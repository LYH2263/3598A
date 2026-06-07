from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from billing.models import (
    BalanceChangeLog,
    ConsumptionRecord,
    RechargeOrder,
    RechargeRecord,
    Wallet,
)
from notices.services import NotificationService


class LedgerService:
    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _next_order_no() -> str:
        return f'RC{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid4().hex[:6].upper()}'

    @staticmethod
    def _create_balance_log(
        *,
        wallet: Wallet,
        change_type: str,
        amount_delta: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        operator: str,
        related_order_no: str = '',
        remark: str = '',
    ) -> BalanceChangeLog:
        return BalanceChangeLog.objects.create(
            user=wallet.user,
            wallet=wallet,
            change_type=change_type,
            amount_delta=LedgerService._money(amount_delta),
            balance_before=LedgerService._money(balance_before),
            balance_after=LedgerService._money(balance_after),
            operator=operator,
            related_order_no=related_order_no,
            remark=remark,
        )

    @staticmethod
    @transaction.atomic
    def create_recharge(user, amount: Decimal, channel: str, operator: str, remark: str = '', order=None):
        amount = LedgerService._money(amount)
        if amount <= 0:
            raise ValidationError('充值金额必须大于 0。')

        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        if wallet.is_frozen:
            raise ValidationError('账户已冻结，无法执行充值入账。')

        balance_before = wallet.balance
        wallet.balance = LedgerService._money(wallet.balance + amount)
        wallet.save(update_fields=['balance', 'updated_at'])

        record = RechargeRecord.objects.create(
            user=user,
            order=order,
            amount=amount,
            channel=channel,
            operator=operator,
            remark=remark,
        )

        LedgerService._create_balance_log(
            wallet=wallet,
            change_type=BalanceChangeLog.TYPE_RECHARGE,
            amount_delta=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            operator=operator,
            related_order_no=order.order_no if order else '',
            remark=remark,
        )

        return record

    @staticmethod
    @transaction.atomic
    def create_recharge_order(user, amount: Decimal, channel: str, submit_remark: str = ''):
        amount = LedgerService._money(amount)
        if amount <= 0:
            raise ValidationError('充值金额必须大于 0。')

        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        if wallet.is_frozen:
            raise ValidationError('账户已冻结，无法提交充值订单。')

        return RechargeOrder.objects.create(
            user=user,
            order_no=LedgerService._next_order_no(),
            amount=amount,
            channel=channel,
            submit_remark=submit_remark,
        )

    @staticmethod
    @transaction.atomic
    def review_recharge_order(order: RechargeOrder, action: str, reviewer, review_remark: str = '') -> RechargeOrder:
        order = RechargeOrder.objects.select_for_update().select_related('user').filter(id=order.id).first()
        if not order:
            raise ValidationError('充值订单不存在。')
        if order.status != RechargeOrder.STATUS_PENDING:
            raise ValidationError('该充值订单已处理，请勿重复审核。')

        if action not in {RechargeOrder.STATUS_APPROVED, RechargeOrder.STATUS_REJECTED}:
            raise ValidationError('非法审核动作。')

        if action == RechargeOrder.STATUS_APPROVED:
            LedgerService.create_recharge(
                user=order.user,
                amount=order.amount,
                channel=order.channel,
                operator=reviewer.username,
                remark=review_remark or '管理员审核通过充值订单',
                order=order,
            )
            order.status = RechargeOrder.STATUS_APPROVED
        else:
            order.status = RechargeOrder.STATUS_REJECTED

        order.reviewer = reviewer
        order.review_remark = review_remark
        order.reviewed_at = timezone.now()
        order.save(update_fields=['status', 'reviewer', 'review_remark', 'reviewed_at', 'updated_at'])

        if action == RechargeOrder.STATUS_APPROVED:
            NotificationService.dispatch_for_user(
                'order_approved',
                order.user,
                {'order_no': order.order_no, 'amount': str(order.amount)},
            )
        else:
            NotificationService.dispatch_for_user(
                'order_rejected',
                order.user,
                {'order_no': order.order_no},
            )

        return order

    @staticmethod
    def _review_single_order(order_id: int, action: str, reviewer, review_remark: str) -> dict:
        try:
            with transaction.atomic():
                order = RechargeOrder.objects.select_for_update().select_related('user', 'user__wallet').filter(id=order_id).first()
                if not order:
                    return {
                        'order_id': order_id,
                        'order_no': '',
                        'success': False,
                        'reason': '充值订单不存在。',
                    }

                order_no = order.order_no

                if order.status != RechargeOrder.STATUS_PENDING:
                    status_label = dict(RechargeOrder.STATUS_CHOICES).get(order.status, order.status)
                    return {
                        'order_id': order_id,
                        'order_no': order_no,
                        'success': False,
                        'reason': f'该订单状态为「{status_label}」，已处理，请勿重复审核。',
                    }

                if action not in {RechargeOrder.STATUS_APPROVED, RechargeOrder.STATUS_REJECTED}:
                    return {
                        'order_id': order_id,
                        'order_no': order_no,
                        'success': False,
                        'reason': '非法审核动作。',
                    }

                if action == RechargeOrder.STATUS_APPROVED:
                    wallet = getattr(order.user, 'wallet', None)
                    if wallet and wallet.is_frozen:
                        frozen_reason = wallet.frozen_reason or '未填写原因'
                        return {
                            'order_id': order_id,
                            'order_no': order_no,
                            'success': False,
                            'reason': f'对应用户账户已冻结（{frozen_reason}），无法入账。',
                        }

                    LedgerService.create_recharge(
                        user=order.user,
                        amount=order.amount,
                        channel=order.channel,
                        operator=reviewer.username,
                        remark=review_remark or '管理员审核通过充值订单',
                        order=order,
                    )
                    order.status = RechargeOrder.STATUS_APPROVED
                else:
                    order.status = RechargeOrder.STATUS_REJECTED

                order.reviewer = reviewer
                order.review_remark = review_remark
                order.reviewed_at = timezone.now()
                order.save(update_fields=['status', 'reviewer', 'review_remark', 'reviewed_at', 'updated_at'])

                if action == RechargeOrder.STATUS_APPROVED:
                    NotificationService.dispatch_for_user(
                        'order_approved',
                        order.user,
                        {'order_no': order.order_no, 'amount': str(order.amount)},
                    )
                else:
                    NotificationService.dispatch_for_user(
                        'order_rejected',
                        order.user,
                        {'order_no': order.order_no},
                    )

                return {
                    'order_id': order_id,
                    'order_no': order_no,
                    'success': True,
                    'reason': '',
                }
        except ValidationError as e:
            msg = e.detail[0] if isinstance(e.detail, list) else str(e.detail)
            return {
                'order_id': order_id,
                'order_no': '',
                'success': False,
                'reason': msg,
            }
        except Exception as e:
            return {
                'order_id': order_id,
                'order_no': '',
                'success': False,
                'reason': f'系统异常：{str(e)}',
            }

    @staticmethod
    def batch_review_recharge_orders(order_ids: list[int], action: str, reviewer, review_remark: str = '') -> dict:
        results = []
        for order_id in order_ids:
            result = LedgerService._review_single_order(order_id, action, reviewer, review_remark)
            results.append(result)

        success_count = sum(1 for r in results if r['success'])
        failure_count = len(results) - success_count

        return {
            'total': len(results),
            'success_count': success_count,
            'failure_count': failure_count,
            'action': action,
            'results': results,
        }

    @staticmethod
    @transaction.atomic
    def freeze_wallet(user, operator: str, reason: str = '') -> Wallet:
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        if wallet.is_frozen:
            return wallet

        balance_before = wallet.balance
        wallet.is_frozen = True
        wallet.frozen_reason = reason
        wallet.frozen_at = timezone.now()
        wallet.save(update_fields=['is_frozen', 'frozen_reason', 'frozen_at', 'updated_at'])

        LedgerService._create_balance_log(
            wallet=wallet,
            change_type=BalanceChangeLog.TYPE_FREEZE,
            amount_delta=Decimal('0.00'),
            balance_before=balance_before,
            balance_after=wallet.balance,
            operator=operator,
            remark=reason or '管理员冻结账户',
        )

        NotificationService.dispatch_for_user(
            'account_frozen',
            user,
            {'reason': reason or '未填写原因'},
        )

        return wallet

    @staticmethod
    @transaction.atomic
    def unfreeze_wallet(user, operator: str, reason: str = '') -> Wallet:
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        if not wallet.is_frozen:
            return wallet

        balance_before = wallet.balance
        wallet.is_frozen = False
        wallet.frozen_reason = ''
        wallet.frozen_at = None
        wallet.save(update_fields=['is_frozen', 'frozen_reason', 'frozen_at', 'updated_at'])

        LedgerService._create_balance_log(
            wallet=wallet,
            change_type=BalanceChangeLog.TYPE_UNFREEZE,
            amount_delta=Decimal('0.00'),
            balance_before=balance_before,
            balance_after=wallet.balance,
            operator=operator,
            remark=reason or '管理员解冻账户',
        )

        NotificationService.dispatch_for_user('account_unfrozen', user)

        return wallet

    @staticmethod
    @transaction.atomic
    def create_consumption(
        user,
        category: str,
        usage: Decimal,
        unit_price: Decimal,
        meter_value: Decimal | None,
        operator: str,
        channel: str = ConsumptionRecord.CHANNEL_MANUAL,
        building: str = '',
        room: str = '',
        remark: str = '',
    ):
        usage = LedgerService._money(usage)
        unit_price = LedgerService._money(unit_price)
        if usage <= 0 or unit_price <= 0:
            raise ValidationError('用量和单价必须大于 0。')

        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        if wallet.is_frozen:
            raise ValidationError('账户已冻结，无法执行消费扣费。')

        cost_amount = LedgerService._money(usage * unit_price)
        if wallet.balance < cost_amount:
            raise ValidationError('余额不足，请先充值。')

        balance_before = wallet.balance
        wallet.balance = LedgerService._money(wallet.balance - cost_amount)
        wallet.save(update_fields=['balance', 'updated_at'])

        record = ConsumptionRecord.objects.create(
            user=user,
            category=category,
            channel=channel,
            usage=usage,
            unit_price=unit_price,
            cost_amount=cost_amount,
            meter_value=meter_value,
            building=building,
            room=room,
            operator=operator,
            remark=remark,
        )

        LedgerService._create_balance_log(
            wallet=wallet,
            change_type=BalanceChangeLog.TYPE_CONSUMPTION,
            amount_delta=LedgerService._money(-cost_amount),
            balance_before=balance_before,
            balance_after=wallet.balance,
            operator=operator,
            remark=remark,
        )

        return record
