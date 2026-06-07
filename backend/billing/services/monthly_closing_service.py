from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from billing.models import (
    BalanceChangeLog,
    ConsumptionRecord,
    MonthlyStatement,
    ReconciliationDiff,
    SettlementRun,
    Wallet,
)

logger = logging.getLogger(__name__)


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _period_start_end(period: str):
    """Parse YYYY-MM and return (start_date, end_date) as timezone-aware datetimes at midnight of the first day, and midnight of the 1st of next month (exclusive)."""
    year, month = map(int, period.split('-'))
    start = datetime(year, month, 1, 0, 0, 0)
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    end = datetime(next_year, next_month, 1, 0, 0, 0)
    tz = timezone.get_current_timezone()
    return tz.localize(start), tz.localize(end)


def _previous_period(period: str) -> str:
    year, month = map(int, period.split('-'))
    if month == 1:
        return f'{year - 1:04d}-12'
    return f'{year:04d}-{month - 1:02d}'


class MonthlyClosingService:

    # ---------- Aggregation helpers ----------

    @staticmethod
    def _aggregate_logs_for_user_period(user: User, period: str):
        start, end = _period_start_end(period)
        logs_qs = BalanceChangeLog.objects.filter(
            user=user,
            created_at__gte=start,
            created_at__lt=end,
        )

        recharge_total = _money(
            logs_qs.filter(change_type=BalanceChangeLog.TYPE_RECHARGE).aggregate(
                t=Sum('amount_delta')
            )['t']
            or 0
        )
        refund_total = _money(
            logs_qs.filter(change_type=BalanceChangeLog.TYPE_REFUND).aggregate(
                t=Sum('amount_delta')
            )['t']
            or 0
        )
        adjust_total = _money(
            logs_qs.filter(change_type=BalanceChangeLog.TYPE_ADJUST).aggregate(
                t=Sum('amount_delta')
            )['t']
            or 0
        )
        cross_month_total = _money(
            logs_qs.filter(change_type=BalanceChangeLog.TYPE_CROSS_MONTH_ADJUST).aggregate(
                t=Sum('amount_delta')
            )['t']
            or 0
        )

        consumption_logs = logs_qs.filter(change_type=BalanceChangeLog.TYPE_CONSUMPTION)

        water_total = _money(0)
        water_count = 0
        electricity_total = _money(0)
        electricity_count = 0

        if consumption_logs.exists():
            related_consumptions = ConsumptionRecord.objects.filter(
                user=user,
                created_at__gte=start,
                created_at__lt=end,
            )
            water_q = related_consumptions.filter(category=ConsumptionRecord.CATEGORY_WATER)
            electricity_q = related_consumptions.filter(category=ConsumptionRecord.CATEGORY_ELECTRICITY)
            water_total = _money(water_q.aggregate(t=Sum('cost_amount'))['t'] or 0)
            water_count = water_q.count()
            electricity_total = _money(electricity_q.aggregate(t=Sum('cost_amount'))['t'] or 0)
            electricity_count = electricity_q.count()

        recharge_count = logs_qs.filter(change_type=BalanceChangeLog.TYPE_RECHARGE).count()
        refund_count = logs_qs.filter(change_type=BalanceChangeLog.TYPE_REFUND).count()
        adjust_count = logs_qs.filter(change_type=BalanceChangeLog.TYPE_ADJUST).count()

        return {
            'recharge_total': recharge_total,
            'recharge_count': recharge_count,
            'water_total': water_total,
            'water_count': water_count,
            'electricity_total': electricity_total,
            'electricity_count': electricity_count,
            'refund_total': refund_total,
            'refund_count': refund_count,
            'adjust_total': adjust_total,
            'adjust_count': adjust_count,
            'cross_month_adjust_total': cross_month_total,
        }

    @staticmethod
    def _get_opening_balance(user: User, period: str) -> Decimal:
        start, _end = _period_start_end(period)
        prev_period = _previous_period(period)
        prev_stmt = MonthlyStatement.objects.filter(
            user=user, period=prev_period, status=MonthlyStatement.STATUS_PUBLISHED
        ).first()
        if prev_stmt is not None:
            return _money(prev_stmt.closing_balance)

        first_log = (
            BalanceChangeLog.objects.filter(user=user, created_at__lt=start)
            .order_by('-created_at')
            .first()
        )
        if first_log is not None:
            return _money(first_log.balance_after)

        wallet, _ = Wallet.objects.get_or_create(user=user)
        return _money(wallet.balance)

    # ---------- Core: generate a single user's statement ----------

    @staticmethod
    @transaction.atomic
    def generate_user_statement(
        user: User,
        period: str,
        operator: str = 'system',
        auto_publish: bool = False,
    ) -> MonthlyStatement:
        """Generate or regenerate the monthly statement for a user for a given period.

        Idempotent: if a draft already exists it will be overwritten.  If a published
        statement already exists this raises unless auto_publish forces a re-run
        (called by explicit re-run which will rollback first).
        """
        existing = MonthlyStatement.objects.select_for_update().filter(
            user=user, period=period
        ).first()

        if existing and existing.status == MonthlyStatement.STATUS_PUBLISHED:
            raise ValueError(
                f'{user.username} 的 {period} 月结已发布，如需重跑请先回滚。'
            )

        agg = MonthlyClosingService._aggregate_logs_for_user_period(user, period)
        opening = MonthlyClosingService._get_opening_balance(user, period)

        consumption_sum = _money(agg['water_total'] + agg['electricity_total'])
        closing = _money(
            opening
            + agg['recharge_total']
            - consumption_sum
            + agg['refund_total']
            + agg['adjust_total']
            + agg['cross_month_adjust_total']
        )

        prev_period = _previous_period(period)
        prev_stmt = MonthlyStatement.objects.filter(
            user=user, period=prev_period
        ).first()

        if existing:
            existing.opening_balance = opening
            existing.recharge_total = agg['recharge_total']
            existing.recharge_count = agg['recharge_count']
            existing.water_total = agg['water_total']
            existing.water_count = agg['water_count']
            existing.electricity_total = agg['electricity_total']
            existing.electricity_count = agg['electricity_count']
            existing.refund_total = agg['refund_total']
            existing.refund_count = agg['refund_count']
            existing.adjust_total = agg['adjust_total']
            existing.adjust_count = agg['adjust_count']
            existing.cross_month_adjust_total = agg['cross_month_adjust_total']
            existing.closing_balance = closing
            existing.previous_statement = prev_stmt
            existing.generated_by = operator
            existing.status = (
                MonthlyStatement.STATUS_PUBLISHED
                if auto_publish
                else MonthlyStatement.STATUS_DRAFT
            )
            existing.closed_at = timezone.now() if auto_publish else None
            existing.save()
            stmt = existing
        else:
            stmt = MonthlyStatement.objects.create(
                user=user,
                period=period,
                opening_balance=opening,
                recharge_total=agg['recharge_total'],
                recharge_count=agg['recharge_count'],
                water_total=agg['water_total'],
                water_count=agg['water_count'],
                electricity_total=agg['electricity_total'],
                electricity_count=agg['electricity_count'],
                refund_total=agg['refund_total'],
                refund_count=agg['refund_count'],
                adjust_total=agg['adjust_total'],
                adjust_count=agg['adjust_count'],
                cross_month_adjust_total=agg['cross_month_adjust_total'],
                closing_balance=closing,
                previous_statement=prev_stmt,
                status=(
                    MonthlyStatement.STATUS_PUBLISHED
                    if auto_publish
                    else MonthlyStatement.STATUS_DRAFT
                ),
                closed_at=timezone.now() if auto_publish else None,
                generated_by=operator,
            )

        if auto_publish:
            MonthlyClosingService._mark_logs_settled(user, period)

        return stmt

    @staticmethod
    def _mark_logs_settled(user: User, period: str) -> None:
        start, end = _period_start_end(period)
        BalanceChangeLog.objects.filter(
            user=user,
            created_at__gte=start,
            created_at__lt=end,
        ).update(is_settled=True, settlement_period=period)

    @staticmethod
    def _unmark_logs_settled(user: User, period: str) -> None:
        BalanceChangeLog.objects.filter(
            user=user,
            settlement_period=period,
        ).update(is_settled=False, settlement_period='')

    # ---------- Publish / rollback ----------

    @staticmethod
    @transaction.atomic
    def publish_statement(statement: MonthlyStatement, operator: str) -> MonthlyStatement:
        statement = MonthlyStatement.objects.select_for_update().get(pk=statement.pk)
        if statement.status == MonthlyStatement.STATUS_PUBLISHED:
            return statement
        if statement.status == MonthlyStatement.STATUS_ROLLED_BACK:
            raise ValueError('已回滚的月结单需重新生成后再发布。')

        MonthlyClosingService._mark_logs_settled(statement.user, statement.period)
        statement.status = MonthlyStatement.STATUS_PUBLISHED
        statement.closed_at = timezone.now()
        statement.generated_by = operator
        statement.save()
        return statement

    @staticmethod
    @transaction.atomic
    def rollback_statement(statement: MonthlyStatement, operator: str) -> MonthlyStatement:
        statement = MonthlyStatement.objects.select_for_update().get(pk=statement.pk)
        if statement.status != MonthlyStatement.STATUS_PUBLISHED:
            return statement

        next_period_stmt = (
            MonthlyStatement.objects.filter(
                user=statement.user,
                previous_statement=statement,
            )
            .exclude(status=MonthlyStatement.STATUS_ROLLED_BACK)
            .first()
        )
        if next_period_stmt:
            raise ValueError(
                f'存在后续已发布月结单 {next_period_stmt.period}，请先回滚后续月份。'
            )

        MonthlyClosingService._unmark_logs_settled(statement.user, statement.period)
        statement.status = MonthlyStatement.STATUS_ROLLED_BACK
        statement.save()
        return statement

    # ---------- Batch runs ----------

    @staticmethod
    def run_monthly_settlement(
        period: str,
        operator: str = 'system',
        auto_publish: bool = True,
        user_id: Optional[int] = None,
    ) -> SettlementRun:
        mode = SettlementRun.MODE_USER if user_id else SettlementRun.MODE_MONTH
        run = SettlementRun.objects.create(
            period=period,
            mode=mode,
            target_user_id=user_id,
            status=SettlementRun.STATUS_RUNNING,
            triggered_by=operator,
        )

        try:
            if user_id:
                users = User.objects.filter(pk=user_id)
            else:
                users = User.objects.filter(is_active=True)

            total = users.count()
            run.total_users = total
            run.save()

            success = 0
            failed = 0
            messages = []

            for u in users.iterator():
                try:
                    with transaction.atomic():
                        existing = MonthlyStatement.objects.filter(
                            user=u, period=period
                        ).first()
                        if existing and existing.status == MonthlyStatement.STATUS_PUBLISHED:
                            MonthlyClosingService.rollback_statement(existing, operator)
                        MonthlyClosingService.generate_user_statement(
                            u, period, operator=operator, auto_publish=auto_publish
                        )
                    success += 1
                except Exception as e:
                    failed += 1
                    msg = f'用户 {u.username}(id={u.id}): {e}'
                    logger.warning(msg)
                    messages.append(msg)

            run.status = SettlementRun.STATUS_SUCCESS if failed == 0 else SettlementRun.STATUS_FAILED
            run.success_count = success
            run.failed_count = failed
            run.message = '\n'.join(messages)
            run.finished_at = timezone.now()
            run.save()
            return run
        except Exception as e:
            run.status = SettlementRun.STATUS_FAILED
            run.message = f'整体失败: {e}'
            run.finished_at = timezone.now()
            run.save()
            logger.exception('run_monthly_settlement failed')
            return run

    # ---------- Reconciliation ----------

    @staticmethod
    def run_reconciliation(operator: str = 'system') -> dict:
        run_id = uuid.uuid4().hex[:16]
        diffs = []

        users = User.objects.filter(is_active=True)
        for u in users.iterator():
            wallet, _ = Wallet.objects.get_or_create(user=u)
            first_log = BalanceChangeLog.objects.filter(user=u).order_by('created_at').first()
            opening_balance = first_log.balance_before if first_log else Decimal('0.00')
            agg = BalanceChangeLog.objects.filter(user=u).aggregate(t=Sum('amount_delta'))
            delta = _money(agg['t'] or 0)
            recalc = _money(opening_balance + delta)
            wallet_bal = _money(wallet.balance)
            diff = _money(recalc - wallet_bal)

            if diff != 0:
                ReconciliationDiff.objects.create(
                    run_id=run_id,
                    user=u,
                    wallet_balance=wallet_bal,
                    recalculated_balance=recalc,
                    difference=diff,
                    detail=f'首笔日志期初:{opening_balance}, 流水累计:{delta}, 重算余额:{recalc}, 钱包余额:{wallet_bal}',
                )
                diffs.append({
                    'user_id': u.id,
                    'username': u.username,
                    'wallet_balance': str(wallet_bal),
                    'recalculated_balance': str(recalc),
                    'difference': str(diff),
                })

        return {
            'run_id': run_id,
            'total_users': users.count(),
            'diff_count': len(diffs),
            'diffs': diffs,
        }

    # ---------- Cross-month adjustment ----------

    @staticmethod
    @transaction.atomic
    def apply_cross_month_adjustment(
        user: User,
        source_period: str,
        target_period: str,
        amount: Decimal,
        operator: str,
        remark: str = '',
    ) -> BalanceChangeLog:
        if target_period <= source_period:
            raise ValueError('目标账期必须晚于来源账期。')

        src_stmt = MonthlyStatement.objects.filter(
            user=user, period=source_period, status=MonthlyStatement.STATUS_PUBLISHED
        ).first()
        if not src_stmt:
            raise ValueError(f'来源账期 {source_period} 尚未发布，无需跨月调整。')

        wallet = Wallet.objects.select_for_update().get(user=user)
        balance_before = wallet.balance
        wallet.balance = _money(wallet.balance + amount)
        wallet.save(update_fields=['balance', 'updated_at'])

        log = BalanceChangeLog.objects.create(
            user=user,
            wallet=wallet,
            change_type=BalanceChangeLog.TYPE_CROSS_MONTH_ADJUST,
            amount_delta=_money(amount),
            balance_before=_money(balance_before),
            balance_after=_money(wallet.balance),
            operator=operator,
            remark=remark or f'跨月调整 来源:{source_period}',
            cross_month_adjust_from=source_period,
            settlement_period=target_period,
        )
        return log
