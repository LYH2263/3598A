from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from billing.models import RechargeOrder
from marketing.models import (
    Coupon,
    Promotion,
    PromotionRedemption,
    UserCoupon,
    UserTagRelation,
)


@dataclass
class AppliedPromotion:
    promotion_id: int
    name: str
    promotion_type: str
    benefit_amount: Decimal = Decimal('0.00')
    description: str = ''


@dataclass
class PromotionCalculationResult:
    original_amount: Decimal
    payable_amount: Decimal = Decimal('0.00')
    credited_amount: Decimal = Decimal('0.00')
    discount_amount: Decimal = Decimal('0.00')
    bonus_amount: Decimal = Decimal('0.00')
    stacking_policy: str = 'allow'
    applied_promotions: list[AppliedPromotion] = field(default_factory=list)
    applied_coupon_id: Optional[int] = None
    applied_coupon_name: str = ''
    coupon_discount_amount: Decimal = Decimal('0.00')
    error: str = ''

    def to_dict(self) -> dict:
        return {
            'original_amount': str(self.original_amount),
            'payable_amount': str(self.payable_amount),
            'credited_amount': str(self.credited_amount),
            'discount_amount': str(self.discount_amount),
            'bonus_amount': str(self.bonus_amount),
            'stacking_policy': self.stacking_policy,
            'applied_promotions': [
                {
                    'promotion_id': p.promotion_id,
                    'name': p.name,
                    'type': p.promotion_type,
                    'benefit_amount': str(p.benefit_amount),
                    'description': p.description,
                    'rule_display': p.description,
                }
                for p in self.applied_promotions
            ],
            'applied_coupon_id': self.applied_coupon_id,
            'applied_coupon_name': self.applied_coupon_name,
            'coupon_discount_amount': str(self.coupon_discount_amount),
            'error': self.error,
        }

    def applied_promotions_to_list(self) -> list[dict]:
        return [
            {
                'promotion_id': p.promotion_id,
                'name': p.name,
                'promotion_type': p.promotion_type,
                'benefit_amount': str(p.benefit_amount),
                'description': p.description,
                'rule_display': p.description,
            }
            for p in self.applied_promotions
        ]


class PromotionEngine:
    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _is_user_in_audience(user, promotion: Promotion) -> bool:
        if promotion.audience_type == Promotion.AUDIENCE_ALL:
            return True
        if promotion.audience_type == Promotion.AUDIENCE_ROLE:
            profile_role = getattr(user.profile, 'role', '')
            allowed = promotion.audience_roles or []
            return profile_role in allowed
        if promotion.audience_type == Promotion.AUDIENCE_TAG:
            tag_ids = promotion.audience_tag_ids or []
            if not tag_ids:
                return True
            return UserTagRelation.objects.filter(
                user=user, tag_id__in=tag_ids
            ).exists()
        return False

    @staticmethod
    def _check_limit(user, promotion: Promotion) -> bool:
        if promotion.limit_type == Promotion.LIMIT_NONE or promotion.limit_count <= 0:
            return True
        qs = PromotionRedemption.objects.filter(user=user, promotion=promotion)
        if promotion.limit_type == Promotion.LIMIT_PER_DAY:
            today = timezone.localdate()
            count = qs.filter(redemption_date=today).count()
        else:
            count = qs.count()
        return count < promotion.limit_count

    @staticmethod
    def _calc_promotion_benefit(promotion: Promotion, amount: Decimal) -> tuple[Decimal, str]:
        cfg = promotion.rule_config or {}
        if promotion.promotion_type == Promotion.TYPE_BONUS:
            threshold = Decimal(str(cfg.get('threshold', '0')))
            bonus = Decimal(str(cfg.get('bonus', '0')))
            if amount >= threshold:
                return bonus, f'充{float(threshold):g}送{float(bonus):g}'
            return Decimal('0'), ''
        if promotion.promotion_type == Promotion.TYPE_DISCOUNT:
            threshold = Decimal(str(cfg.get('threshold', '0')))
            discount = Decimal(str(cfg.get('discount', '0')))
            if amount >= threshold:
                return discount, f'满{float(threshold):g}减{float(discount):g}'
            return Decimal('0'), ''
        if promotion.promotion_type == Promotion.TYPE_TIERED_CASHBACK:
            tiers = cfg.get('tiers', [])
            best_rate = Decimal('0')
            best_threshold = Decimal('0')
            for tier in tiers:
                try:
                    t = Decimal(str(tier.get('threshold', '0')))
                    r = Decimal(str(tier.get('rate', '0')))
                except Exception:
                    continue
                if amount >= t and r > best_rate:
                    best_rate = r
                    best_threshold = t
            if best_rate > 0:
                cashback = PromotionEngine._money(amount * best_rate)
                pct = float(best_rate * 100)
                desc = f'达{float(best_threshold):g}返{pct:.0f}%（返现{float(cashback):g}元）'
                return cashback, desc
            return Decimal('0'), ''
        return Decimal('0'), ''

    @staticmethod
    def _get_stacking_policy(promotions: list[Promotion], coupon: Optional[UserCoupon]) -> str:
        policies = {p.stacking_policy for p in promotions}
        if not promotions and not coupon:
            return Promotion.STACK_ALLOW
        strict_order = [
            Promotion.STACK_PROMO_ONLY,
            Promotion.STACK_COUPON_ONLY,
            Promotion.STACK_EXCLUSIVE,
            Promotion.STACK_ALLOW,
        ]
        for p in strict_order:
            if p in policies:
                return p
        return Promotion.STACK_ALLOW

    @staticmethod
    def _evaluate_coupon(coupon: Optional[UserCoupon], amount: Decimal) -> tuple[Decimal, str]:
        if not coupon:
            return Decimal('0'), ''
        template = coupon.coupon
        if amount < template.min_amount:
            return Decimal('0'), f'未达使用门槛{template.min_amount}元'
        now = timezone.now()
        if now < template.valid_from or now > template.valid_until:
            return Decimal('0'), '优惠券不在有效期内'
        if template.coupon_type == Coupon.TYPE_FIXED:
            discount = min(template.face_value, amount)
            return discount, f'{template.face_value}元券'
        if template.coupon_type == Coupon.TYPE_PERCENT:
            discount = PromotionEngine._money(amount * (Decimal('1') - template.discount_rate))
            if template.max_discount:
                discount = min(discount, template.max_discount)
            return discount, f'{template.discount_rate*10:.1f}折券'
        return Decimal('0'), ''

    @staticmethod
    def calculate(
        user,
        amount: Decimal,
        coupon_id: Optional[int] = None,
    ) -> PromotionCalculationResult:
        amount = PromotionEngine._money(amount)
        result = PromotionCalculationResult(original_amount=amount)

        if amount <= 0:
            result.error = '充值金额必须大于0'
            result.payable_amount = amount
            result.credited_amount = amount
            return result

        now = timezone.now()
        active_promotions = list(
            Promotion.objects.filter(
                is_active=True,
                start_time__lte=now,
                end_time__gte=now,
            ).order_by('-id')
        )

        eligible_promotions = []
        for promo in active_promotions:
            if not PromotionEngine._is_user_in_audience(user, promo):
                continue
            if not PromotionEngine._check_limit(user, promo):
                continue
            benefit, desc = PromotionEngine._calc_promotion_benefit(promo, amount)
            if benefit > 0:
                eligible_promotions.append((promo, benefit, desc))

        user_coupon: Optional[UserCoupon] = None
        if coupon_id:
            user_coupon = UserCoupon.objects.filter(
                id=coupon_id,
                user=user,
                status=UserCoupon.STATUS_AVAILABLE,
            ).select_related('coupon').first()

        stacking_policy = PromotionEngine._get_stacking_policy(
            [p for p, _, _ in eligible_promotions], user_coupon
        )
        result.stacking_policy = stacking_policy

        promo_objs_to_apply = []
        coupon_to_apply: Optional[UserCoupon] = None

        if stacking_policy == Promotion.STACK_PROMO_ONLY:
            promo_objs_to_apply = eligible_promotions
        elif stacking_policy == Promotion.STACK_COUPON_ONLY:
            coupon_to_apply = user_coupon
        elif stacking_policy == Promotion.STACK_EXCLUSIVE:
            promo_best_benefit = sum(b for _, b, _ in eligible_promotions)
            coupon_benefit, _ = PromotionEngine._evaluate_coupon(user_coupon, amount) if user_coupon else (Decimal('0'), '')
            if promo_best_benefit >= coupon_benefit and eligible_promotions:
                promo_objs_to_apply = eligible_promotions
            elif user_coupon and coupon_benefit > 0:
                coupon_to_apply = user_coupon
        else:
            promo_objs_to_apply = eligible_promotions
            coupon_to_apply = user_coupon

        total_bonus = Decimal('0')
        total_promo_discount = Decimal('0')
        for promo, benefit, desc in promo_objs_to_apply:
            if promo.promotion_type in (Promotion.TYPE_BONUS, Promotion.TYPE_TIERED_CASHBACK):
                total_bonus += benefit
            elif promo.promotion_type == Promotion.TYPE_DISCOUNT:
                total_promo_discount += benefit
            result.applied_promotions.append(AppliedPromotion(
                promotion_id=promo.id,
                name=promo.name,
                promotion_type=promo.promotion_type,
                benefit_amount=PromotionEngine._money(benefit),
                description=desc,
            ))

        coupon_discount = Decimal('0')
        if coupon_to_apply:
            coupon_discount, _desc = PromotionEngine._evaluate_coupon(coupon_to_apply, amount)
            coupon_discount = min(coupon_discount, amount)
            result.applied_coupon_id = coupon_to_apply.id
            result.applied_coupon_name = coupon_to_apply.coupon.name
            result.coupon_discount_amount = PromotionEngine._money(coupon_discount)

        total_discount = total_promo_discount + coupon_discount
        payable = max(amount - total_discount, Decimal('0'))
        credited = payable + total_bonus

        result.discount_amount = PromotionEngine._money(total_discount)
        result.bonus_amount = PromotionEngine._money(total_bonus)
        result.payable_amount = PromotionEngine._money(payable)
        result.credited_amount = PromotionEngine._money(credited)

        return result

    @staticmethod
    @transaction.atomic
    def apply_on_approve(order: RechargeOrder, reviewer_username: str) -> tuple[str, Decimal, Decimal]:
        remark_parts = []
        total_bonus = Decimal('0')
        total_discount = Decimal('0')

        applied_promotions = order.applied_promotions or []
        today = timezone.localdate()
        for p in applied_promotions:
            promo = Promotion.objects.filter(id=p.get('promotion_id')).first()
            benefit = Decimal(str(p.get('benefit_amount', '0')))
            if promo:
                if promo.promotion_type in (Promotion.TYPE_BONUS, Promotion.TYPE_TIERED_CASHBACK):
                    total_bonus += benefit
                elif promo.promotion_type == Promotion.TYPE_DISCOUNT:
                    total_discount += benefit
                PromotionRedemption.objects.create(
                    user=order.user,
                    promotion=promo,
                    order_no=order.order_no,
                    original_amount=order.amount,
                    benefit_amount=benefit,
                    redemption_date=today,
                )
                remark_parts.append(f"[{promo.get_promotion_type_display()}:{promo.name}] {p.get('description','')} 赠送/优惠{benefit}元")

        if order.coupon_id:
            user_coupon = UserCoupon.objects.select_for_update().filter(
                id=order.coupon_id,
                user=order.user,
                status=UserCoupon.STATUS_AVAILABLE,
            ).first()
            if user_coupon:
                coupon_discount = order.discount_amount if order.discount_amount > 0 else Decimal('0')
                user_coupon.status = UserCoupon.STATUS_USED
                user_coupon.used_at = timezone.now()
                user_coupon.used_order_no = order.order_no
                user_coupon.discount_amount = coupon_discount
                user_coupon.save(update_fields=['status', 'used_at', 'used_order_no', 'discount_amount'])
                total_discount += coupon_discount
                remark_parts.append(f"[优惠券:{user_coupon.coupon.name}] 优惠{coupon_discount}元")

        remark = '；'.join(remark_parts) if remark_parts else ''
        return remark, PromotionEngine._money(total_bonus), PromotionEngine._money(total_discount)
