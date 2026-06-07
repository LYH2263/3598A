from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.utils import timezone

from billing.models import (
    ConsumptionRecord,
    PriceStrategy,
    PriceTier,
    PriceTimeSlot,
)
from housing.models import Room, StayRecord


@dataclass
class BillingBreakdownItem:
    label: str
    usage: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass
class BillingResult:
    success: bool
    strategy_id: Optional[int] = None
    strategy_name: str = ''
    strategy_type: str = ''
    scope_label: str = ''
    total_usage: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    breakdown: list[BillingBreakdownItem] = field(default_factory=list)
    error: str = ''

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'scope_label': self.scope_label,
            'total_usage': str(self.total_usage),
            'total_amount': str(self.total_amount),
            'breakdown': [
                {
                    'label': b.label,
                    'usage': str(b.usage),
                    'unit_price': str(b.unit_price),
                    'amount': str(b.amount),
                }
                for b in self.breakdown
            ],
            'error': self.error,
        }

    def to_remark(self) -> str:
        if not self.success:
            return self.error or '计费失败'
        parts = [f'策略：{self.strategy_name}（{self.scope_label}）']
        for b in self.breakdown:
            parts.append(f'{b.label}: {b.usage}*{b.unit_price}={b.amount}')
        parts.append(f'合计：{self.total_amount}元')
        return '；'.join(parts)


class PricingService:
    DEFAULT_UNIT_PRICE = {
        ConsumptionRecord.CATEGORY_WATER: Decimal('5.00'),
        ConsumptionRecord.CATEGORY_ELECTRICITY: Decimal('0.60'),
    }

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _infer_user_room(user: User, at_time: Optional[datetime] = None) -> Optional[Room]:
        at_time = at_time or timezone.now()
        qs = StayRecord.objects.filter(
            user=user,
            status=StayRecord.STATUS_ACTIVE,
            start_date__lte=at_time.date(),
        ).select_related('bed__room__floor__building__campus')
        stay = qs.filter(Q(end_date__isnull=True) | Q(end_date__gte=at_time.date())).first()
        if stay:
            return stay.bed.room
        return None

    @staticmethod
    def _find_strategy(
        category: str,
        at_date: date,
        room: Optional[Room] = None,
    ) -> Optional[PriceStrategy]:
        base_qs = PriceStrategy.objects.filter(
            category=category,
            is_active=True,
            effective_from__lte=at_date,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=at_date)
        ).order_by('-priority', '-effective_from')

        if room:
            s = base_qs.filter(scope_type=PriceStrategy.SCOPE_ROOM, room_id=room.id).first()
            if s:
                return s
            s = base_qs.filter(scope_type=PriceStrategy.SCOPE_BUILDING, building_id=room.floor.building.id).first()
            if s:
                return s
            s = base_qs.filter(scope_type=PriceStrategy.SCOPE_CAMPUS, campus_id=room.floor.building.campus.id).first()
            if s:
                return s

        s = base_qs.filter(scope_type=PriceStrategy.SCOPE_GLOBAL).first()
        return s

    @staticmethod
    def _calc_monthly_usage_before(
        user: User,
        category: str,
        at_time: datetime,
    ) -> Decimal:
        start = datetime(at_time.year, at_time.month, 1, 0, 0, 0)
        current_tz = timezone.get_current_timezone()
        start_local = current_tz.localize(start)
        total = (
            ConsumptionRecord.objects.filter(
                user=user,
                category=category,
                created_at__gte=start_local,
                created_at__lt=at_time,
            ).aggregate(t=Sum('usage'))['t'] or Decimal('0')
        )
        return PricingService._money(total)

    @staticmethod
    def _calc_fixed(
        strategy: PriceStrategy,
        usage: Decimal,
    ) -> BillingResult:
        price = Decimal('0')
        if strategy.strategy_type == PriceStrategy.TYPE_FIXED:
            tiers = list(strategy.tiers.all())
            if tiers:
                price = tiers[0].unit_price
        result = BillingResult(
            success=True,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            scope_label=strategy.scope_label(),
            total_usage=usage,
            total_amount=PricingService._money(usage * price),
        )
        result.breakdown.append(BillingBreakdownItem(
            label='固定单价',
            usage=usage,
            unit_price=price,
            amount=result.total_amount,
        ))
        return result

    @staticmethod
    def _calc_tiered(
        strategy: PriceStrategy,
        usage: Decimal,
        prior_usage: Decimal,
    ) -> BillingResult:
        tiers = list(strategy.tiers.all().order_by('sort_order', 'min_usage'))
        result = BillingResult(
            success=True,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            scope_label=strategy.scope_label(),
            total_usage=usage,
        )
        if not tiers:
            result.success = False
            result.error = '阶梯策略未配置任何分段'
            return result

        start_cum = prior_usage
        remaining = usage
        total = Decimal('0')
        for tier in tiers:
            if remaining <= 0:
                break
            t_min = tier.min_usage
            t_max = tier.max_usage
            if t_max is None:
                in_tier = max(Decimal('0'), remaining)
            else:
                capacity = t_max - max(t_min, start_cum)
                if capacity <= 0:
                    continue
                in_tier = min(remaining, capacity)
            in_tier = PricingService._money(in_tier)
            if in_tier <= 0:
                continue
            amount = PricingService._money(in_tier * tier.unit_price)
            total += amount
            result.breakdown.append(BillingBreakdownItem(
                label=f'{t_min}~{t_max if t_max else "∞"}档',
                usage=in_tier,
                unit_price=tier.unit_price,
                amount=amount,
            ))
            remaining -= in_tier
            start_cum += in_tier

        if remaining > 0 and tiers:
            last = tiers[-1]
            if last.max_usage is None:
                amount = PricingService._money(remaining * last.unit_price)
                total += amount
                result.breakdown.append(BillingBreakdownItem(
                    label=f'{last.min_usage}~∞档',
                    usage=remaining,
                    unit_price=last.unit_price,
                    amount=amount,
                ))

        result.total_amount = PricingService._money(total)
        return result

    @staticmethod
    def _calc_timeslot(
        strategy: PriceStrategy,
        usage: Decimal,
        at_time: datetime,
    ) -> BillingResult:
        slots = list(strategy.timeslots.all().order_by('sort_order', 'start_time'))
        result = BillingResult(
            success=True,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            scope_label=strategy.scope_label(),
            total_usage=usage,
        )
        if not slots:
            result.success = False
            result.error = '时段策略未配置任何时段'
            return result

        t = at_time.time()
        weekday = at_time.weekday()
        matched_slot = None
        for slot in slots:
            if not slot.weekday_contains(weekday):
                continue
            if slot.start_time <= slot.end_time:
                if slot.start_time <= t < slot.end_time:
                    matched_slot = slot
                    break
            else:
                if t >= slot.start_time or t < slot.end_time:
                    matched_slot = slot
                    break

        if matched_slot is None:
            matched_slot = slots[0]

        amount = PricingService._money(usage * matched_slot.unit_price)
        result.total_amount = amount
        result.breakdown.append(BillingBreakdownItem(
            label=f'{matched_slot.name}（{matched_slot.start_time}-{matched_slot.end_time}）',
            usage=usage,
            unit_price=matched_slot.unit_price,
            amount=amount,
        ))
        return result

    @staticmethod
    def calculate(
        user: User,
        category: str,
        usage: Decimal,
        at_time: Optional[datetime] = None,
        room: Optional[Room] = None,
    ) -> BillingResult:
        at_time = at_time or timezone.now()
        usage = PricingService._money(usage)
        if usage <= 0:
            return BillingResult(success=False, error='用量必须大于0')

        if room is None:
            room = PricingService._infer_user_room(user, at_time)

        strategy = PricingService._find_strategy(category, at_time.date(), room)
        if strategy is None:
            default_price = PricingService.DEFAULT_UNIT_PRICE.get(category, Decimal('0.00'))
            result = BillingResult(
                success=True,
                strategy_name='默认价格',
                strategy_type=PriceStrategy.TYPE_FIXED,
                scope_label='系统默认',
                total_usage=usage,
                total_amount=PricingService._money(usage * default_price),
            )
            result.breakdown.append(BillingBreakdownItem(
                label='系统默认单价',
                usage=usage,
                unit_price=default_price,
                amount=result.total_amount,
            ))
            return result

        try:
            if strategy.strategy_type == PriceStrategy.TYPE_FIXED:
                return PricingService._calc_fixed(strategy, usage)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIERED:
                prior = PricingService._calc_monthly_usage_before(user, category, at_time)
                return PricingService._calc_tiered(strategy, usage, prior)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIMESLOT:
                return PricingService._calc_timeslot(strategy, usage, at_time)
            else:
                return BillingResult(success=False, error=f'未知策略类型：{strategy.strategy_type}')
        except Exception as e:
            return BillingResult(success=False, error=f'计费异常：{str(e)}')

    @staticmethod
    def preview(
        user: Optional[User],
        category: str,
        usage: Decimal,
        at_time: datetime,
        room: Optional[Room] = None,
    ) -> BillingResult:
        usage = PricingService._money(usage)
        if usage <= 0:
            return BillingResult(success=False, error='用量必须大于0')

        if room is None and user is not None:
            room = PricingService._infer_user_room(user, at_time)

        strategy = PricingService._find_strategy(category, at_time.date(), room)
        if strategy is None:
            default_price = PricingService.DEFAULT_UNIT_PRICE.get(category, Decimal('0.00'))
            result = BillingResult(
                success=True,
                strategy_name='默认价格',
                strategy_type=PriceStrategy.TYPE_FIXED,
                scope_label='系统默认',
                total_usage=usage,
                total_amount=PricingService._money(usage * default_price),
            )
            result.breakdown.append(BillingBreakdownItem(
                label='系统默认单价',
                usage=usage,
                unit_price=default_price,
                amount=result.total_amount,
            ))
            return result

        try:
            if strategy.strategy_type == PriceStrategy.TYPE_FIXED:
                return PricingService._calc_fixed(strategy, usage)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIERED:
                prior = Decimal('0')
                if user is not None:
                    prior = PricingService._calc_monthly_usage_before(user, category, at_time)
                return PricingService._calc_tiered(strategy, usage, prior)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIMESLOT:
                return PricingService._calc_timeslot(strategy, usage, at_time)
            else:
                return BillingResult(success=False, error=f'未知策略类型：{strategy.strategy_type}')
        except Exception as e:
            return BillingResult(success=False, error=f'计费异常：{str(e)}')
