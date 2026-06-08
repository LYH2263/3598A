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


def _money(value) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _period_start_end(period: str):
    """Parse YYYY-MM -> (start_aware_dt, end_aware_dt).

    end is exclusive (midnight on 1st of next month).
    """
    year, month = map(int, period.split('-'))
    start = datetime(year, month, 1, 0, 0, 0)
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    end = datetime(next_year, next_month, 1, 0, 0, 0)
    return timezone.make_aware(start), timezone.make_aware(end)


def _previous_period(period: str) -> str:
    year, month = map(int, period.split('-'))
    if month == 1:
        return f'{year - 1:04d}-12'
    return f'{year:04d}-{month - 1:02d}'


class MonthlyClosingService:
    """Financial monthly settlement service.

    All public methods are **idempotent**: calling them multiple times with the same
    inputs produces the same result as calling them once.
    """

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_logs(user: User, start, end):
        """Aggregate BalanceChangeLog + ConsumptionRecord for [start, end)."""
        logs_qs = BalanceChangeLog.objects.filter(
            user=user,
            created_at__gte=start,
            created_at__lt=end,
        )

        def _sum(qs):
            return _money(qs.aggregate(t=Sum('amount_delta'))['t'] or 0)

        recharge_total = _sum(logs_qs.filter(change_type=BalanceChangeLog.TYPE_RECHARGE))
        refund_total = _sum(logs_qs.filter(change_type=BalanceChangeLog.TYPE_REFUND))
        adjust_total = _sum(logs_qs.filter(change_type=BalanceChangeLog.TYPE_ADJUST))
        cross_month_total = _sum(logs_qs.filter(change_type=BalanceChangeLog.TYPE_CROSS_MONTH_ADJUST))

        recharge_count = logs_qs.filter(change_type=BalanceChangeLog.TYPE_RECHARGE).count()
        refund_count = logs_qs.filter(change_type=BalanceChangeLog.TYPE_REFUND).count()
        adjust_count = logs_qs.filter(change_type=BalanceChangeLog.TYPE_ADJUST).count()

        water_total = _money(0)
        water_count = 0
        electricity_total = _money(0)
        electricity_count = 0

        cons = ConsumptionRecord.objects.filter(
            user=user,
            created_at__gte=start,
            created_at__lt=end,
        )
        water_q = cons.filter(category=ConsumptionRecord.CATEGORY_WATER)
        electricity_q = cons.filter(category=ConsumptionRecord.CATEGORY_ELECTRICITY)
        water_total = _money(water_q.aggregate(t=Sum('cost_amount'))['t'] or 0)
        water_count = water_q.count()
        electricity_total = _money(electricity_q.aggregate(t=Sum('cost_amount'))['t'] or 0)
        electricity_count = electricity_q.count()

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
    def _opening_balance(user: User, period: str, start) -> Decimal:
        """Compute the opening balance for *period*.

        Priority:
        1) previous month's published statement closing balance
        2) the balance_after of the latest log strictly before *start*
        3) the user's current wallet balance (fresh user case)
        """
        prev_period = _previous_period(period)
        prev_stmt = MonthlyStatement.objects.filter(
            user=user,
            period=prev_period,
            status=MonthlyStatement.STATUS_PUBLISHED,
        ).first()
        if prev_stmt is not None:
            return _money(prev_stmt.closing_balance)

        last_log = (
            BalanceChangeLog.objects.filter(user=user, created_at__lt=start)
            .order_by('-created_at')
            .first()
        )
        if last_log is not None:
            return _money(last_log.balance_after)

        wallet, _ = Wallet.objects.get_or_create(user=user)
        return _money(wallet.balance)

    @staticmethod
    def _mark_settled(user: User, period: str, start, end):
        BalanceChangeLog.objects.filter(
            user=user,
            created_at__gte=start,
            created_at__lt=end,
        ).update(is_settled=True, settlement_period=period)

    @staticmethod
    def _unmark_settled(user: User, period: str):
        BalanceChangeLog.objects.filter(
            user=user,
            settlement_period=period,
        ).update(is_settled=False, settlement_period='')

    # ------------------------------------------------------------------
    # Public: single user statement
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def generate_user_statement(
        user: User,
        period: str,
        operator: str = 'system',
        auto_publish: bool = False,
    ) -> MonthlyStatement:
        """Generate (or regenerate) the monthly statement for one user.

        Idempotent: a ``draft`` statement is overwritten; a ``published`` one raises
        ValueError (call :meth:`rollback_statement` first, or use
        :meth:`run_monthly_settlement` which does this automatically).
        """
        start, end = _period_start_end(period)

        existing = (
            MonthlyStatement.objects.select_for_update()
            .filter(user=user, period=period)
            .first()
        )
        if existing and existing.status == MonthlyStatement.STATUS_PUBLISHED:
            raise ValueError(
                f'{user.username} 的 {period} 月结已发布，如需重跑请先回滚。'
            )

        agg = MonthlyClosingService._aggregate_logs(user, start, end)
        opening = MonthlyClosingService._opening_balance(user, period, start)
        consumption_sum = _money(agg['water_total'] + agg['electricity_total'])
        closing = _money(
            opening
            + agg['recharge_total']
            - consumption_sum
            + agg['refund_total']
            + agg['adjust_total']
            + agg['cross_month_adjust_total']
        )

        prev_stmt = MonthlyStatement.objects.filter(
            user=user, period=_previous_period(period)
        ).first()

        target_status = (
            MonthlyStatement.STATUS_PUBLISHED
            if auto_publish
            else MonthlyStatement.STATUS_DRAFT
        )
        closed_at = timezone.now() if auto_publish else None

        fields = dict(
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
            status=target_status,
            closed_at=closed_at,
            generated_by=operator,
        )

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.save()
            stmt = existing
        else:
            stmt = MonthlyStatement.objects.create(user=user, period=period, **fields)

        if auto_publish:
            MonthlyClosingService._mark_settled(user, period, start, end)

        return stmt

    # ------------------------------------------------------------------
    # Public: publish / rollback
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def publish_statement(statement: MonthlyStatement, operator: str) -> MonthlyStatement:
        start, end = _period_start_end(statement.period)
        qs = MonthlyStatement.objects.select_for_update().filter(pk=statement.pk)
        stmt = qs.first()
        if stmt is None:
            raise ValueError('月结单不存在。')
        if stmt.status == MonthlyStatement.STATUS_PUBLISHED:
            return stmt
        if stmt.status == MonthlyStatement.STATUS_ROLLED_BACK:
            raise ValueError('已回滚的月结单需重新生成后再发布。')

        MonthlyClosingService._mark_settled(stmt.user, stmt.period, start, end)
        stmt.status = MonthlyStatement.STATUS_PUBLISHED
        stmt.closed_at = timezone.now()
        stmt.generated_by = operator
        stmt.save()
        return stmt

    @staticmethod
    @transaction.atomic
    def rollback_statement(statement: MonthlyStatement, operator: str) -> MonthlyStatement:
        qs = MonthlyStatement.objects.select_for_update().filter(pk=statement.pk)
        stmt = qs.first()
        if stmt is None:
            raise ValueError('月结单不存在。')
        if stmt.status != MonthlyStatement.STATUS_PUBLISHED:
            return stmt

        blocker = (
            MonthlyStatement.objects.filter(
                user=stmt.user,
                previous_statement=stmt,
            )
            .exclude(status=MonthlyStatement.STATUS_ROLLED_BACK)
            .first()
        )
        if blocker:
            raise ValueError(
                f'存在后续已发布月结单 {blocker.period}，请先回滚后续月份。'
            )

        MonthlyClosingService._unmark_settled(stmt.user, stmt.period)
        stmt.status = MonthlyStatement.STATUS_ROLLED_BACK
        stmt.save()
        return stmt

    # ------------------------------------------------------------------
    # Public: batch settlement run
    # ------------------------------------------------------------------

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
            users_qs = User.objects.filter(is_active=True)
            if user_id:
                users_qs = users_qs.filter(pk=user_id)
            user_ids = list(users_qs.values_list('pk', flat=True))
            total = len(user_ids)
            run.total_users = total
            run.save()

            success = 0
            failed = 0
            errors = []
            start, end = _period_start_end(period)  # noqa: F841 - sanity check period format

            for uid in user_ids:
                try:
                    user = User.objects.get(pk=uid)
                    with transaction.atomic():
                        existing = (
                            MonthlyStatement.objects.select_for_update()
                            .filter(user=user, period=period)
                            .first()
                        )
                        if existing and existing.status == MonthlyStatement.STATUS_PUBLISHED:
                            MonthlyClosingService.rollback_statement(existing, operator)
                        MonthlyClosingService.generate_user_statement(
                            user, period, operator=operator, auto_publish=auto_publish
                        )
                    success += 1
                except Exception as exc:
                    failed += 1
                    msg = f'用户 id={uid}: {exc}'
                    logger.warning(msg)
                    errors.append(msg)

            run.status = (
                SettlementRun.STATUS_SUCCESS if failed == 0 else SettlementRun.STATUS_FAILED
            )
            run.success_count = success
            run.failed_count = failed
            run.message = '\n'.join(errors)
            run.finished_at = timezone.now()
            run.save()
            return run
        except Exception as exc:
            logger.exception('run_monthly_settlement failed for period=%s', period)
            run.status = SettlementRun.STATUS_FAILED
            run.message = f'整体失败: {exc}'
            run.finished_at = timezone.now()
            run.save()
            return run

    # ------------------------------------------------------------------
    # Public: reconciliation
    # ------------------------------------------------------------------

    @staticmethod
    def run_reconciliation(operator: str = 'system') -> dict:
        run_id = uuid.uuid4().hex[:16]
        diffs = []

        user_ids = list(User.objects.filter(is_active=True).values_list('pk', flat=True))
        for uid in user_ids:
            user = User.objects.get(pk=uid)
            wallet, _ = Wallet.objects.get_or_create(user=user)
            first_log = (
                BalanceChangeLog.objects.filter(user=user).order_by('created_at').first()
            )
            opening = first_log.balance_before if first_log else Decimal('0.00')
            delta = _money(
                BalanceChangeLog.objects.filter(user=user).aggregate(t=Sum('amount_delta'))['t']
                or 0
            )
            recalc = _money(Decimal(opening) + delta)
            wallet_bal = _money(wallet.balance)
            difference = _money(recalc - wallet_bal)

            if difference != 0:
                ReconciliationDiff.objects.create(
                    run_id=run_id,
                    user=user,
                    wallet_balance=wallet_bal,
                    recalculated_balance=recalc,
                    difference=difference,
                    detail=(
                        f'首笔日志期初={opening}, 流水累计={delta}, '
                        f'重算余额={recalc}, 钱包余额={wallet_bal}'
                    ),
                )
                diffs.append(
                    {
                        'user_id': user.id,
                        'username': user.username,
                        'wallet_balance': str(wallet_bal),
                        'recalculated_balance': str(recalc),
                        'difference': str(difference),
                    }
                )

        return {
            'run_id': run_id,
            'total_users': len(user_ids),
            'diff_count': len(diffs),
            'diffs': diffs,
        }

    # ------------------------------------------------------------------
    # Public: cross-month adjustment
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def apply_cross_month_adjustment(
        user: User,
        source_period: str,
        target_period: str,
        amount,
        operator: str,
        remark: str = '',
    ) -> BalanceChangeLog:
        """Apply an adjustment that logically belongs to *source_period* but
        must be posted in *target_period* because the source is already closed.

        The adjustment log is flagged with both ``cross_month_adjust_from`` and
        ``settlement_period=target_period`` so that the next settlement picks it up.
        """
        if target_period <= source_period:
            raise ValueError('目标账期必须晚于来源账期。')

        src_stmt = MonthlyStatement.objects.filter(
            user=user,
            period=source_period,
            status=MonthlyStatement.STATUS_PUBLISHED,
        ).first()
        if not src_stmt:
            raise ValueError(f'来源账期 {source_period} 尚未发布，无需跨月调整。')

        wallet = Wallet.objects.select_for_update().get(user=user)
        balance_before = _money(wallet.balance)
        amount_d = _money(amount)
        wallet.balance = _money(wallet.balance + amount_d)
        wallet.save(update_fields=['balance', 'updated_at'])

        log = BalanceChangeLog.objects.create(
            user=user,
            wallet=wallet,
            change_type=BalanceChangeLog.TYPE_CROSS_MONTH_ADJUST,
            amount_delta=amount_d,
            balance_before=balance_before,
            balance_after=_money(wallet.balance),
            operator=operator,
            remark=remark or f'跨月调整 来源:{source_period}',
            cross_month_adjust_from=source_period,
            settlement_period=target_period,
        )
        return log
