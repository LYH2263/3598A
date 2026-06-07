from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from marketing.models import Coupon, UserCoupon, UserTagRelation


class CouponService:
    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _gen_code() -> str:
        return f'CP{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid4().hex[:8].upper()}'

    @staticmethod
    def _is_user_eligible(user, coupon: Coupon) -> bool:
        tag_ids = coupon.audience_tag_ids or []
        if not tag_ids:
            return True
        return UserTagRelation.objects.filter(user=user, tag_id__in=tag_ids).exists()

    @staticmethod
    @transaction.atomic
    def grant_coupon_to_user(
        coupon: Coupon,
        user: User,
        granted_by: User | None = None,
        custom_expire=None,
    ) -> UserCoupon:
        if not coupon.is_active:
            raise ValidationError('该优惠券已下架。')

        now = timezone.now()
        if now < coupon.valid_from or now > coupon.valid_until:
            raise ValidationError('该优惠券不在发放时间范围内。')

        if coupon.total_quantity > 0 and coupon.issued_count >= coupon.total_quantity:
            raise ValidationError('该优惠券已发放完毕。')

        if not CouponService._is_user_eligible(user, coupon):
            raise ValidationError('当前用户不符合该优惠券的领取条件。')

        owned = UserCoupon.objects.filter(user=user, coupon=coupon).count()
        if coupon.per_user_limit > 0 and owned >= coupon.per_user_limit:
            raise ValidationError(f'每人限领 {coupon.per_user_limit} 张，已达上限。')

        expired_at = custom_expire if custom_expire else coupon.valid_until
        user_coupon = UserCoupon.objects.create(
            user=user,
            coupon=coupon,
            status=UserCoupon.STATUS_AVAILABLE,
            code=CouponService._gen_code(),
            expired_at=expired_at,
            granted_by=granted_by,
        )

        coupon.issued_count += 1
        coupon.save(update_fields=['issued_count', 'updated_at'])

        return user_coupon

    @staticmethod
    @transaction.atomic
    def grant_coupon_to_users(
        coupon: Coupon,
        user_ids: list[int],
        granted_by: User | None = None,
    ) -> dict:
        results = []
        for uid in user_ids:
            user = User.objects.filter(id=uid).first()
            if not user:
                results.append({'user_id': uid, 'success': False, 'reason': '用户不存在'})
                continue
            try:
                CouponService.grant_coupon_to_user(coupon, user, granted_by=granted_by)
                results.append({'user_id': uid, 'username': user.username, 'success': True})
            except ValidationError as e:
                results.append({
                    'user_id': uid,
                    'username': user.username,
                    'success': False,
                    'reason': str(e.detail),
                })
            except Exception as e:
                results.append({
                    'user_id': uid,
                    'username': user.username,
                    'success': False,
                    'reason': str(e),
                })

        success = sum(1 for r in results if r['success'])
        return {
            'total': len(results),
            'success_count': success,
            'failure_count': len(results) - success,
            'results': results,
        }

    @staticmethod
    @transaction.atomic
    def public_claim(coupon: Coupon, user: User) -> UserCoupon:
        if coupon.scope != Coupon.SCOPE_PUBLIC:
            raise ValidationError('该优惠券非公开领取。')
        return CouponService.grant_coupon_to_user(coupon, user)

    @staticmethod
    @transaction.atomic
    def revoke_user_coupon(user_coupon_id: int, reason: str = '', operator: str = '') -> UserCoupon:
        uc = UserCoupon.objects.select_for_update().filter(id=user_coupon_id).first()
        if not uc:
            raise ValidationError('用户优惠券不存在。')
        if uc.status != UserCoupon.STATUS_AVAILABLE:
            raise ValidationError('仅可回收可用状态的优惠券。')
        uc.status = UserCoupon.STATUS_REVOKED
        uc.revoked_at = timezone.now()
        uc.revoked_reason = reason or f'管理员回收，操作人：{operator}'
        uc.save(update_fields=['status', 'revoked_at', 'revoked_reason'])

        coupon = uc.coupon
        if coupon.issued_count > 0:
            coupon.issued_count -= 1
            coupon.save(update_fields=['issued_count', 'updated_at'])

        return uc

    @staticmethod
    @transaction.atomic
    def mark_expired_coupons() -> int:
        now = timezone.now()
        count = UserCoupon.objects.filter(
            status=UserCoupon.STATUS_AVAILABLE,
            expired_at__lt=now,
        ).update(status=UserCoupon.STATUS_EXPIRED)
        return count

    @staticmethod
    def list_user_coupons(user, status: str = '') -> list[UserCoupon]:
        qs = UserCoupon.objects.filter(user=user).select_related('coupon')
        if status:
            qs = qs.filter(status=status)
        return list(qs.order_by('-granted_at'))
