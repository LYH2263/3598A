from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q

from marketing.models import Coupon, Promotion, PromotionRedemption, UserCoupon


class MarketingReportService:
    @staticmethod
    def promotion_summary(promotion_id: int | None = None) -> list[dict]:
        qs = Promotion.objects.all().order_by('-id')
        if promotion_id:
            qs = qs.filter(id=promotion_id)
        result = []
        for promo in qs:
            redemptions = PromotionRedemption.objects.filter(promotion=promotion)
            unique_users = redemptions.values('user_id').distinct().count()
            total_benefit = redemptions.aggregate(total=Sum('benefit_amount'))['total'] or 0
            total_recharge = redemptions.aggregate(total=Sum('original_amount'))['total'] or 0
            result.append({
                'promotion_id': promo.id,
                'name': promo.name,
                'type': promo.promotion_type,
                'type_display': promo.get_promotion_type_display(),
                'is_active': promo.is_active,
                'start_time': promo.start_time.isoformat() if promo.start_time else '',
                'end_time': promo.end_time.isoformat() if promo.end_time else '',
                'redemption_count': redemptions.count(),
                'unique_user_count': unique_users,
                'total_benefit_amount': str(total_benefit),
                'total_recharge_amount': str(total_recharge),
            })
        return result

    @staticmethod
    def coupon_summary(coupon_id: int | None = None) -> list[dict]:
        qs = Coupon.objects.all().order_by('-id')
        if coupon_id:
            qs = qs.filter(id=coupon_id)
        result = []
        for coupon in qs:
            instances = UserCoupon.objects.filter(coupon=coupon)
            claimed = instances.count()
            used = instances.filter(status=UserCoupon.STATUS_USED).count()
            expired = instances.filter(status=UserCoupon.STATUS_EXPIRED).count()
            revoked = instances.filter(status=UserCoupon.STATUS_REVOKED).count()
            total_discount = instances.filter(status=UserCoupon.STATUS_USED).aggregate(
                total=Sum('discount_amount')
            )['total'] or 0
            used_orders = instances.filter(status=UserCoupon.STATUS_USED).exclude(used_order_no='')
            from billing.models import RechargeOrder
            order_ids = list(used_orders.values_list('used_order_no', flat=True))
            total_recharge = RechargeOrder.objects.filter(
                order_no__in=order_ids, status=RechargeOrder.STATUS_APPROVED
            ).aggregate(total=Sum('amount'))['total'] or 0
            result.append({
                'coupon_id': coupon.id,
                'name': coupon.name,
                'type': coupon.coupon_type,
                'type_display': coupon.get_coupon_type_display(),
                'is_active': coupon.is_active,
                'scope': coupon.scope,
                'scope_display': coupon.get_scope_display(),
                'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else '',
                'valid_until': coupon.valid_until.isoformat() if coupon.valid_until else '',
                'total_quantity': coupon.total_quantity,
                'claimed_count': claimed,
                'used_count': used,
                'expired_count': expired,
                'revoked_count': revoked,
                'total_discount_amount': str(total_discount),
                'driven_recharge_amount': str(total_recharge),
            })
        return result

    @staticmethod
    def overall_summary() -> dict:
        promos = Promotion.objects.count()
        active_promos = Promotion.objects.filter(is_active=True).count()
        coupons = Coupon.objects.count()
        active_coupons = Coupon.objects.filter(is_active=True).count()
        total_redemption = PromotionRedemption.objects.count()
        total_coupon_used = UserCoupon.objects.filter(status=UserCoupon.STATUS_USED).count()
        total_benefit = PromotionRedemption.objects.aggregate(total=Sum('benefit_amount'))['total'] or 0
        total_coupon_discount = UserCoupon.objects.filter(
            status=UserCoupon.STATUS_USED
        ).aggregate(total=Sum('discount_amount'))['total'] or 0
        return {
            'promotion_count': promos,
            'active_promotion_count': active_promos,
            'coupon_template_count': coupons,
            'active_coupon_template_count': active_coupons,
            'total_promotion_redemption_count': total_redemption,
            'total_coupon_used_count': total_coupon_used,
            'total_promotion_benefit_amount': str(total_benefit),
            'total_coupon_discount_amount': str(total_coupon_discount),
        }
