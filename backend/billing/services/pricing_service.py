from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.auth.models import User
from django.db.models import Prefetch, Q, Sum
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
    tier_start: Optional[Decimal] = None
    tier_end: Optional[Decimal] = None
    weekday: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class BillingResult:
    success: bool
    strategy_id: Optional[int] = None
    strategy_name: str = ''
    strategy_type: str = ''
    scope_label: str = ''
    category: str = ''
    total_usage: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    prior_monthly_usage: Optional[Decimal] = None
    billed_at: Optional[datetime] = None
    breakdown: list[BillingBreakdownItem] = field(default_factory=list)
    error: str = ''
    error_message: str = ''

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'scope_label': self.scope_label,
            'category': self.category,
            'total_usage': str(self.total_usage),
            'total_amount': str(self.total_amount),
            'prior_monthly_usage': str(self.prior_monthly_usage) if self.prior_monthly_usage is not None else None,
            'billed_at': self.billed_at.isoformat() if self.billed_at else None,
            'breakdown': [
                {
                    'label': b.label,
                    'usage': str(b.usage),
                    'unit_price': str(b.unit_price),
                    'amount': str(b.amount),
                    'tier_start': str(b.tier_start) if b.tier_start is not None else None,
                    'tier_end': str(b.tier_end) if b.tier_end is not None else None,
                    'weekday': b.weekday,
                    'start_time': b.start_time,
                    'end_time': b.end_time,
                }
                for b in self.breakdown
            ],
            'error': self.error,
            'error_message': self.error_message or self.error,
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
        ).prefetch_related(
            Prefetch('tiers', queryset=PriceTier.objects.all().order_by('sort_order', 'min_usage')),
            Prefetch('timeslots', queryset=PriceTimeSlot.objects.all().order_by('sort_order', 'start_time')),
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
        tiers = list(getattr(strategy, 'tiers_list', None) or strategy.tiers.all())
        price = tiers[0].unit_price if tiers else Decimal('0')
        amount = PricingService._money(usage * price)
        result = BillingResult(
            success=True,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            scope_label=strategy.scope_label(),
            total_usage=usage,
            total_amount=amount,
        )
        result.breakdown.append(BillingBreakdownItem(
            label='固定单价',
            usage=usage,
            unit_price=price,
            amount=amount,
            tier_start=tiers[0].min_usage if tiers else None,
            tier_end=tiers[0].max_usage if tiers else None,
        ))
        return result

    @staticmethod
    def _calc_tiered(
        strategy: PriceStrategy,
        usage: Decimal,
        prior_usage: Decimal,
    ) -> BillingResult:
        tiers = list(getattr(strategy, 'tiers_list', None) or strategy.tiers.all())
        result = BillingResult(
            success=True,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            scope_label=strategy.scope_label(),
            total_usage=usage,
            prior_monthly_usage=prior_usage,
        )
        if not tiers:
            result.success = False
            result.error = '阶梯策略未配置任何分段'
            result.error_message = '阶梯策略未配置任何分段'
            return result

        start_cum = prior_usage
        end_cum = prior_usage + usage
        total = Decimal('0')
        BIG = Decimal('999999999999.99')

        for tier in tiers:
            t_min = tier.min_usage
            t_max = tier.max_usage if tier.max_usage is not None else BIG
            overlap_start = max(start_cum, t_min)
            overlap_end = min(end_cum, t_max)

            if overlap_end <= overlap_start:
                continue

            in_tier = PricingService._money(overlap_end - overlap_start)
            if in_tier <= 0:
                continue

            amount = PricingService._money(in_tier * tier.unit_price)
            total += amount
            label_max = '∞' if tier.max_usage is None else str(tier.max_usage)
            result.breakdown.append(BillingBreakdownItem(
                label=f'[{t_min}, {label_max})档',
                usage=in_tier,
                unit_price=tier.unit_price,
                amount=amount,
                tier_start=tier.min_usage,
                tier_end=tier.max_usage,
            ))

        result.total_amount = PricingService._money(total)
        if not result.breakdown:
            result.success = False
            result.error = '用量未命中任何阶梯分段'
            result.error_message = '用量未命中任何阶梯分段，请检查策略分段配置'
        return result

    @staticmethod
    def _calc_timeslot(
        strategy: PriceStrategy,
        usage: Decimal,
        at_time: datetime,
    ) -> BillingResult:
        slots = list(getattr(strategy, 'timeslots_list', None) or strategy.timeslots.all())
        result = BillingResult(
            success=True,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            scope_label=strategy.scope_label(),
            total_usage=usage,
            billed_at=at_time,
        )
        if not slots:
            result.success = False
            result.error = '时段策略未配置任何时段'
            result.error_message = '时段策略未配置任何时段'
            return result

        t = at_time.time()
        weekday = at_time.weekday()
        matched_slot = None
        for slot in slots:
            if not slot.weekday_contains(weekday):
                continue
            s_start = slot.start_time
            s_end = slot.end_time
            if s_start <= s_end:
                if s_start <= t < s_end:
                    matched_slot = slot
                    break
            else:
                if t >= s_start or t < s_end:
                    matched_slot = slot
                    break

        if matched_slot is None:
            matched_slot = slots[0]

        amount = PricingService._money(usage * matched_slot.unit_price)
        result.total_amount = amount
        start_str = matched_slot.start_time.strftime('%H:%M:%S') if hasattr(matched_slot.start_time, 'strftime') else str(matched_slot.start_time)
        end_str = matched_slot.end_time.strftime('%H:%M:%S') if hasattr(matched_slot.end_time, 'strftime') else str(matched_slot.end_time)
        result.breakdown.append(BillingBreakdownItem(
            label=f'{matched_slot.name}（{start_str[:5]}-{end_str[:5]}）',
            usage=usage,
            unit_price=matched_slot.unit_price,
            amount=amount,
            weekday=weekday,
            start_time=start_str,
            end_time=end_str,
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
            r = BillingResult(success=False, error='用量必须大于0', error_message='用量必须大于0')
            r.category = category
            r.billed_at = at_time
            return r

        if room is None:
            room = PricingService._infer_user_room(user, at_time)

        strategy = PricingService._find_strategy(category, at_time.date(), room)
        if strategy is None:
            default_price = PricingService.DEFAULT_UNIT_PRICE.get(category, Decimal('0.00'))
            amount = PricingService._money(usage * default_price)
            result = BillingResult(
                success=True,
                strategy_name='默认价格',
                strategy_type=PriceStrategy.TYPE_FIXED,
                scope_label='系统默认',
                category=category,
                total_usage=usage,
                total_amount=amount,
                billed_at=at_time,
            )
            result.breakdown.append(BillingBreakdownItem(
                label='系统默认单价',
                usage=usage,
                unit_price=default_price,
                amount=amount,
            ))
            return result

        try:
            if strategy.strategy_type == PriceStrategy.TYPE_FIXED:
                r = PricingService._calc_fixed(strategy, usage)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIERED:
                prior = PricingService._calc_monthly_usage_before(user, category, at_time)
                r = PricingService._calc_tiered(strategy, usage, prior)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIMESLOT:
                r = PricingService._calc_timeslot(strategy, usage, at_time)
            else:
                r = BillingResult(success=False, error=f'未知策略类型：{strategy.strategy_type}', error_message=f'未知策略类型：{strategy.strategy_type}')
            r.category = category
            r.billed_at = r.billed_at or at_time
            return r
        except Exception as e:
            import traceback
            return BillingResult(
                success=False,
                error=f'计费异常：{str(e)}',
                error_message=f'计费异常：{str(e)}',
                category=category,
                billed_at=at_time,
            )

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
            r = BillingResult(success=False, error='用量必须大于0', error_message='用量必须大于0')
            r.category = category
            r.billed_at = at_time
            return r

        if room is None and user is not None:
            room = PricingService._infer_user_room(user, at_time)

        strategy = PricingService._find_strategy(category, at_time.date(), room)
        if strategy is None:
            default_price = PricingService.DEFAULT_UNIT_PRICE.get(category, Decimal('0.00'))
            amount = PricingService._money(usage * default_price)
            result = BillingResult(
                success=True,
                strategy_name='默认价格',
                strategy_type=PriceStrategy.TYPE_FIXED,
                scope_label='系统默认',
                category=category,
                total_usage=usage,
                total_amount=amount,
                billed_at=at_time,
            )
            result.breakdown.append(BillingBreakdownItem(
                label='系统默认单价',
                usage=usage,
                unit_price=default_price,
                amount=amount,
            ))
            return result

        try:
            if strategy.strategy_type == PriceStrategy.TYPE_FIXED:
                r = PricingService._calc_fixed(strategy, usage)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIERED:
                prior = Decimal('0')
                if user is not None:
                    prior = PricingService._calc_monthly_usage_before(user, category, at_time)
                r = PricingService._calc_tiered(strategy, usage, prior)
            elif strategy.strategy_type == PriceStrategy.TYPE_TIMESLOT:
                r = PricingService._calc_timeslot(strategy, usage, at_time)
            else:
                r = BillingResult(success=False, error=f'未知策略类型：{strategy.strategy_type}', error_message=f'未知策略类型：{strategy.strategy_type}')
            r.category = category
            r.billed_at = r.billed_at or at_time
            return r
        except Exception as e:
            return BillingResult(
                success=False,
                error=f'计费异常：{str(e)}',
                error_message=f'计费异常：{str(e)}',
                category=category,
                billed_at=at_time,
            )

    @staticmethod
    def preview_compare(
        user: Optional[User],
        category: str,
        usage: Decimal,
        at_time: datetime,
        room: Optional[Room] = None,
    ) -> dict:
        """一次性以三种策略方式进行试算，用于对比展示。"""
        usage = PricingService._money(usage)
        if usage <= 0:
            return {'error': '用量必须大于0'}

        if room is None and user is not None:
            room = PricingService._infer_user_room(user, at_time)

        strategy = PricingService._find_strategy(category, at_time.date(), room)
        default_price = PricingService.DEFAULT_UNIT_PRICE.get(category, Decimal('0.00'))

        def _result(name, strategy_type, scope_label, amount, breakdown_items, prior=None):
            r = BillingResult(
                success=True,
                strategy_name=name,
                strategy_type=strategy_type,
                scope_label=scope_label,
                category=category,
                total_usage=usage,
                total_amount=PricingService._money(amount),
                billed_at=at_time,
                prior_monthly_usage=prior,
            )
            r.breakdown = breakdown_items
            return r

        results = {}

        # 1) 固定单价：取命中策略中的第一个分段单价，或用默认价格
        try:
            if strategy and list(getattr(strategy, 'tiers_list', None) or strategy.tiers.all()):
                tiers = list(getattr(strategy, 'tiers_list', None) or strategy.tiers.all())
                price = tiers[0].unit_price
                amt = usage * price
                bd = [BillingBreakdownItem(label='固定单价（试算）', usage=usage, unit_price=price, amount=PricingService._money(amt), tier_start=tiers[0].min_usage, tier_end=tiers[0].max_usage)]
                results['fixed'] = _result(strategy.name + '(固定试算)', 'fixed', strategy.scope_label(), amt, bd)
            else:
                amt = usage * default_price
                bd = [BillingBreakdownItem(label='系统默认单价', usage=usage, unit_price=default_price, amount=PricingService._money(amt))]
                results['fixed'] = _result('默认价格（固定试算）', 'fixed', '系统默认', amt, bd)
        except Exception as e:
            results['fixed'] = BillingResult(success=False, error=f'固定单价试算失败：{str(e)}', error_message=f'固定单价试算失败：{str(e)}', strategy_type='fixed')

        # 2) 阶梯单价
        try:
            prior = Decimal('0')
            if user is not None:
                prior = PricingService._calc_monthly_usage_before(user, category, at_time)
            if strategy and list(getattr(strategy, 'tiers_list', None) or strategy.tiers.all()):
                mock_strategy = strategy
                r = PricingService._calc_tiered(mock_strategy, usage, prior)
                r.strategy_name = strategy.name + '(阶梯试算)'
                r.strategy_type = 'tiered'
                r.category = category
                r.billed_at = at_time
                results['tiered'] = r
            else:
                amt = usage * default_price
                bd = [BillingBreakdownItem(label='系统默认单价（阶梯试算无配置）', usage=usage, unit_price=default_price, amount=PricingService._money(amt))]
                results['tiered'] = _result('默认价格（阶梯无策略）', 'tiered', '系统默认', amt, bd, prior=prior)
        except Exception as e:
            results['tiered'] = BillingResult(success=False, error=f'阶梯单价试算失败：{str(e)}', error_message=f'阶梯单价试算失败：{str(e)}', strategy_type='tiered')

        # 3) 时段单价
        try:
            if strategy and list(getattr(strategy, 'timeslots_list', None) or strategy.timeslots.all()):
                r = PricingService._calc_timeslot(strategy, usage, at_time)
                r.strategy_name = strategy.name + '(时段试算)'
                r.strategy_type = 'timeslot'
                r.category = category
                r.billed_at = at_time
                results['timeslot'] = r
            else:
                amt = usage * default_price
                bd = [BillingBreakdownItem(label='系统默认单价（时段试算无配置）', usage=usage, unit_price=default_price, amount=PricingService._money(amt))]
                results['timeslot'] = _result('默认价格（时段无策略）', 'timeslot', '系统默认', amt, bd)
        except Exception as e:
            results['timeslot'] = BillingResult(success=False, error=f'时段单价试算失败：{str(e)}', error_message=f'时段单价试算失败：{str(e)}', strategy_type='timeslot')

        # 当前命中的真实策略
        matched = PricingService.preview(user, category, usage, at_time, room)

        return {
            'matched': matched.to_dict(),
            'fixed': results['fixed'].to_dict(),
            'tiered': results['tiered'].to_dict(),
            'timeslot': results['timeslot'].to_dict(),
        }
