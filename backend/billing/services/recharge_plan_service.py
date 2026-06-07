from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from billing.models import (
    PlanExecution,
    RechargeOrder,
    RechargePlan,
    Wallet,
)
from billing.services.ledger_service import LedgerService
from notices.services import NotificationService


class RechargePlanService:
    @staticmethod
    @transaction.atomic
    def create_plan(
        user,
        name: str,
        amount: Decimal,
        period: str,
        channel: str,
        start_date,
        end_date,
        failure_action: str = RechargePlan.FAILURE_ACTION_SKIP,
    ) -> RechargePlan:
        amount = LedgerService._money(amount)
        if amount <= 0:
            raise ValidationError('充值金额必须大于 0。')
        if start_date >= end_date:
            raise ValidationError('结束日期必须晚于开始日期。')
        if start_date < timezone.now().date():
            raise ValidationError('开始日期不能早于今天。')
        if period not in dict(RechargePlan.PERIOD_CHOICES):
            raise ValidationError('不支持的周期类型。')
        if channel not in dict(RechargeOrder.CHANNEL_CHOICES):
            raise ValidationError('不支持的渠道类型。')

        plan = RechargePlan.objects.create(
            user=user,
            name=name.strip() or '自动充值计划',
            amount=amount,
            period=period,
            channel=channel,
            start_date=start_date,
            end_date=end_date,
            next_execution_date=start_date,
            failure_action=failure_action,
            created_by=user.username,
        )

        NotificationService.dispatch_for_user(
            'plan_created',
            user,
            {
                'plan_name': plan.name,
                'amount': str(plan.amount),
                'period': plan.get_period_display(),
                'start_date': str(plan.start_date),
                'end_date': str(plan.end_date),
            },
        )

        return plan

    @staticmethod
    @transaction.atomic
    def pause_plan(plan: RechargePlan, user=None, reason: str = '') -> RechargePlan:
        if plan.status not in {RechargePlan.STATUS_ACTIVE}:
            raise ValidationError('只有执行中的计划才能暂停。')
        plan.status = RechargePlan.STATUS_PAUSED
        plan.paused_at = timezone.now()
        plan.save(update_fields=['status', 'paused_at', 'updated_at'])

        NotificationService.dispatch_for_user(
            'plan_paused',
            plan.user,
            {'plan_name': plan.name, 'reason': reason or '用户主动暂停'},
        )
        return plan

    @staticmethod
    @transaction.atomic
    def resume_plan(plan: RechargePlan) -> RechargePlan:
        if plan.status != RechargePlan.STATUS_PAUSED:
            raise ValidationError('只有已暂停的计划才能恢复。')
        if plan.next_execution_date < timezone.now().date():
            plan.next_execution_date = timezone.now().date()
        plan.status = RechargePlan.STATUS_ACTIVE
        plan.paused_at = None
        plan.save(update_fields=['status', 'paused_at', 'next_execution_date', 'updated_at'])

        NotificationService.dispatch_for_user(
            'plan_resumed',
            plan.user,
            {'plan_name': plan.name},
        )
        return plan

    @staticmethod
    @transaction.atomic
    def end_plan(plan: RechargePlan, reason: str = '') -> RechargePlan:
        if plan.status in {RechargePlan.STATUS_ENDED, RechargePlan.STATUS_EXPIRED}:
            return plan
        plan.status = RechargePlan.STATUS_ENDED
        plan.ended_at = timezone.now()
        plan.end_reason = reason or '用户提前结束'
        plan.save(update_fields=['status', 'ended_at', 'end_reason', 'updated_at'])

        NotificationService.dispatch_for_user(
            'plan_ended',
            plan.user,
            {'plan_name': plan.name, 'reason': plan.end_reason},
        )
        return plan

    @staticmethod
    def get_upcoming_executions(user, days: int = 7) -> list:
        today = timezone.now().date()
        end_day = today + timezone.timedelta(days=days)
        plans = RechargePlan.objects.filter(
            user=user,
            status=RechargePlan.STATUS_ACTIVE,
            next_execution_date__gte=today,
            next_execution_date__lte=end_day,
        ).order_by('next_execution_date')
        result = []
        for p in plans:
            delta = (p.next_execution_date - today).days
            if delta == 0:
                countdown_text = '今天'
            elif delta == 1:
                countdown_text = '明天'
            else:
                countdown_text = f'{delta} 天后'
            result.append({
                'plan_id': p.id,
                'plan_name': p.name,
                'amount': str(p.amount),
                'period': p.period,
                'period_display': p.get_period_display(),
                'next_execution_date': str(p.next_execution_date),
                'countdown_days': delta,
                'countdown_text': countdown_text,
                'channel': p.channel,
                'channel_display': p.get_channel_display() if hasattr(p, 'get_channel_display') else p.channel,
            })
        return result

    @staticmethod
    @transaction.atomic
    def execute_due_plans(operator: str = 'system') -> dict:
        today = timezone.now().date()
        due_plans = RechargePlan.objects.select_for_update().select_related('user', 'user__wallet').filter(
            status=RechargePlan.STATUS_ACTIVE,
            next_execution_date__lte=today,
        )

        total = 0
        success = 0
        failed = 0
        skipped = 0
        errors = []

        for plan in due_plans:
            total += 1
            result = RechargePlanService._execute_single_plan(plan, today, operator)
            if result['status'] == 'success':
                success += 1
            elif result['status'] == 'failed':
                failed += 1
                errors.append({'plan_id': plan.id, 'reason': result['reason']})
            elif result['status'] == 'skipped':
                skipped += 1

        expired_plans = RechargePlan.objects.filter(
            status=RechargePlan.STATUS_ACTIVE,
            end_date__lt=today,
        )
        for p in expired_plans:
            p.status = RechargePlan.STATUS_EXPIRED
            p.ended_at = timezone.now()
            p.end_reason = '计划已到期'
            p.save(update_fields=['status', 'ended_at', 'end_reason', 'updated_at'])

        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'expired_count': expired_plans.count(),
            'errors': errors,
        }

    @staticmethod
    def _execute_single_plan(plan: RechargePlan, today, operator: str) -> dict:
        execution = PlanExecution.objects.create(
            plan=plan,
            user=plan.user,
            scheduled_date=plan.next_execution_date,
            amount=plan.amount,
            channel=plan.channel,
            status=PlanExecution.STATUS_PENDING,
        )

        try:
            wallet = Wallet.objects.filter(user=plan.user).first()
            if wallet and wallet.is_frozen:
                frozen_reason = wallet.frozen_reason or '账户已冻结'
                execution.status = PlanExecution.STATUS_FAILED
                execution.failure_reason = f'账户已冻结：{frozen_reason}'
                execution.executed_at = timezone.now()
                execution.save(update_fields=['status', 'failure_reason', 'executed_at'])
                RechargePlanService._handle_execution_failure(plan, execution, '账户冻结')
                return {'status': 'failed', 'reason': execution.failure_reason}

            order = LedgerService.create_recharge_order(
                user=plan.user,
                amount=plan.amount,
                channel=plan.channel,
                submit_remark=f'来自自动充值计划：{plan.name}',
            )
            execution.order = order
            execution.status = PlanExecution.STATUS_SUCCESS
            execution.executed_at = timezone.now()
            execution.save(update_fields=['order', 'status', 'executed_at'])

            plan.last_execution_date = today
            plan.total_executions += 1
            plan.success_count += 1
            next_date = plan.compute_next_execution_date(today)
            if next_date > plan.end_date:
                plan.status = RechargePlan.STATUS_EXPIRED
                plan.ended_at = timezone.now()
                plan.end_reason = '计划已到期自动结束'
                plan.next_execution_date = plan.end_date
            else:
                plan.next_execution_date = next_date
            plan.save(update_fields=[
                'last_execution_date', 'total_executions', 'success_count',
                'next_execution_date', 'status', 'ended_at', 'end_reason', 'updated_at',
            ])

            NotificationService.dispatch_for_user(
                'plan_execution_success',
                plan.user,
                {
                    'plan_name': plan.name,
                    'amount': str(plan.amount),
                    'order_no': order.order_no,
                    'scheduled_date': str(execution.scheduled_date),
                },
            )
            return {'status': 'success'}

        except ValidationError as e:
            msg = e.detail[0] if isinstance(e.detail, list) else str(e.detail)
            execution.status = PlanExecution.STATUS_FAILED
            execution.failure_reason = msg
            execution.executed_at = timezone.now()
            execution.save(update_fields=['status', 'failure_reason', 'executed_at'])
            RechargePlanService._handle_execution_failure(plan, execution, msg)
            return {'status': 'failed', 'reason': msg}
        except Exception as e:
            msg = f'系统异常：{str(e)}'
            execution.status = PlanExecution.STATUS_FAILED
            execution.failure_reason = msg
            execution.executed_at = timezone.now()
            execution.save(update_fields=['status', 'failure_reason', 'executed_at'])
            RechargePlanService._handle_execution_failure(plan, execution, msg)
            return {'status': 'failed', 'reason': msg}

    @staticmethod
    def _handle_execution_failure(plan: RechargePlan, execution: PlanExecution, reason: str):
        plan.total_executions += 1
        plan.failure_count += 1

        if plan.failure_action == RechargePlan.FAILURE_ACTION_PAUSE:
            plan.status = RechargePlan.STATUS_PAUSED
            plan.paused_at = timezone.now()
        else:
            today = timezone.now().date()
            next_date = plan.compute_next_execution_date(today)
            if next_date > plan.end_date:
                plan.status = RechargePlan.STATUS_EXPIRED
                plan.ended_at = timezone.now()
                plan.end_reason = '计划已到期'
                plan.next_execution_date = plan.end_date
            else:
                plan.next_execution_date = next_date
                execution.status = PlanExecution.STATUS_SKIPPED
                execution.save(update_fields=['status'])

        plan.save(update_fields=[
            'total_executions', 'failure_count', 'status', 'paused_at',
            'next_execution_date', 'ended_at', 'end_reason', 'updated_at',
        ])

        NotificationService.dispatch_for_user(
            'plan_execution_failed',
            plan.user,
            {
                'plan_name': plan.name,
                'scheduled_date': str(execution.scheduled_date),
                'reason': reason,
                'action_taken': (
                    '计划已暂停，请处理后手动恢复'
                    if plan.failure_action == RechargePlan.FAILURE_ACTION_PAUSE
                    else '已跳过本次执行，下次按计划继续'
                ),
            },
        )
