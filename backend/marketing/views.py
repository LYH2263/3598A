from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import IsAdminRole
from marketing.models import Coupon, Promotion, UserCoupon, UserTag, UserTagRelation
from marketing.serializers import (
    CouponGrantSerializer,
    CouponRevokeSerializer,
    CouponSerializer,
    PromotionCalculateSerializer,
    PromotionSerializer,
    UserCouponSerializer,
    UserTagAssignSerializer,
    UserTagSerializer,
)
from marketing.services.coupon_service import CouponService
from marketing.services.promotion_engine import PromotionEngine
from marketing.services.report_service import MarketingReportService


# ========== 用户标签 ==========

class UserTagListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        tags = UserTag.objects.all().order_by('-id')
        return Response(UserTagSerializer(tags, many=True).data)

    def post(self, request):
        serializer = UserTagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserTagDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, tag_id: int):
        tag = UserTag.objects.filter(id=tag_id).first()
        if not tag:
            return Response({'detail': '标签不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserTagSerializer(tag).data)

    def put(self, request, tag_id: int):
        tag = UserTag.objects.filter(id=tag_id).first()
        if not tag:
            return Response({'detail': '标签不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserTagSerializer(tag, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, tag_id: int):
        tag = UserTag.objects.filter(id=tag_id).first()
        if not tag:
            return Response({'detail': '标签不存在。'}, status=status.HTTP_404_NOT_FOUND)
        tag.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserTagAssignAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, tag_id: int, action: str):
        tag = UserTag.objects.filter(id=tag_id).first()
        if not tag:
            return Response({'detail': '标签不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserTagAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data['user_ids']
        if action == 'assign':
            created = 0
            for uid in user_ids:
                _, c = UserTagRelation.objects.get_or_create(user_id=uid, tag=tag)
                if c:
                    created += 1
            return Response({'assigned': created, 'total_input': len(user_ids)})
        elif action == 'remove':
            deleted, _ = UserTagRelation.objects.filter(user_id__in=user_ids, tag=tag).delete()
            return Response({'removed': deleted})
        return Response({'detail': '未知操作。'}, status=status.HTTP_400_BAD_REQUEST)


# ========== 营销活动 ==========

class PromotionListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        is_active = request.query_params.get('is_active', '').strip()
        ptype = request.query_params.get('type', '').strip()
        qs = Promotion.objects.all().order_by('-id')
        if is_active in ('true', 'false'):
            qs = qs.filter(is_active=(is_active == 'true'))
        if ptype:
            qs = qs.filter(promotion_type=ptype)
        return Response(PromotionSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = PromotionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PromotionDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, promotion_id: int):
        promo = Promotion.objects.filter(id=promotion_id).first()
        if not promo:
            return Response({'detail': '活动不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PromotionSerializer(promo).data)

    def put(self, request, promotion_id: int):
        promo = Promotion.objects.filter(id=promotion_id).first()
        if not promo:
            return Response({'detail': '活动不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PromotionSerializer(promo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, promotion_id: int):
        promo = Promotion.objects.filter(id=promotion_id).first()
        if not promo:
            return Response({'detail': '活动不存在。'}, status=status.HTTP_404_NOT_FOUND)
        promo.is_active = False
        promo.save(update_fields=['is_active', 'updated_at'])
        return Response(PromotionSerializer(promo).data)


# ========== 优惠券模板 ==========

class CouponListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        is_active = request.query_params.get('is_active', '').strip()
        scope = request.query_params.get('scope', '').strip()
        qs = Coupon.objects.all().order_by('-id')
        if is_active in ('true', 'false'):
            qs = qs.filter(is_active=(is_active == 'true'))
        if scope:
            qs = qs.filter(scope=scope)
        return Response(CouponSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = CouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CouponDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, coupon_id: int):
        coupon = Coupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({'detail': '优惠券不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CouponSerializer(coupon).data)

    def put(self, request, coupon_id: int):
        coupon = Coupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({'detail': '优惠券不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CouponSerializer(coupon, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, coupon_id: int):
        coupon = Coupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({'detail': '优惠券不存在。'}, status=status.HTTP_404_NOT_FOUND)
        coupon.is_active = False
        coupon.save(update_fields=['is_active', 'updated_at'])
        return Response(CouponSerializer(coupon).data)


class CouponGrantAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = CouponGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        coupon = Coupon.objects.filter(id=data['coupon_id']).first()
        if not coupon:
            return Response({'detail': '优惠券不存在。'}, status=status.HTTP_404_NOT_FOUND)

        user_ids = list(data.get('user_ids') or [])
        for uname in data.get('usernames') or []:
            u = User.objects.filter(username=uname).first()
            if u and u.id not in user_ids:
                user_ids.append(u.id)

        if not user_ids:
            return Response({'detail': '未指定目标用户。'}, status=status.HTTP_400_BAD_REQUEST)

        result = CouponService.grant_coupon_to_users(coupon, user_ids, granted_by=request.user)
        return Response(result)


class CouponPublicClaimAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, coupon_id: int):
        coupon = Coupon.objects.filter(id=coupon_id).first()
        if not coupon:
            return Response({'detail': '优惠券不存在。'}, status=status.HTTP_404_NOT_FOUND)
        try:
            user_coupon = CouponService.public_claim(coupon, request.user)
        except ValidationError as e:
            return Response({'detail': str(e.detail)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserCouponSerializer(user_coupon).data, status=status.HTTP_201_CREATED)


# ========== 用户优惠券 ==========

class UserCouponListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status', '').strip()
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role == Profile.ROLE_ADMIN:
            user_id = request.query_params.get('user_id', '').strip()
            if user_id:
                coupons = CouponService.list_user_coupons(User(id=int(user_id)), status_filter)
            else:
                coupons = list(
                    UserCoupon.objects.all().select_related('coupon').order_by('-granted_at')[:500]
                )
        else:
            coupons = CouponService.list_user_coupons(request.user, status_filter)
        return Response(UserCouponSerializer(coupons, many=True).data)


class UserCouponAvailableForRechargeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        now = timezone.now()
        coupons = UserCoupon.objects.filter(
            user=request.user,
            status=UserCoupon.STATUS_AVAILABLE,
            expired_at__gte=now,
        ).select_related('coupon').order_by('-granted_at')
        return Response(UserCouponSerializer(coupons, many=True).data)


class UserCouponRevokeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, user_coupon_id: int):
        serializer = CouponRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            uc = CouponService.revoke_user_coupon(
                user_coupon_id,
                reason=serializer.validated_data.get('reason', ''),
                operator=request.user.username,
            )
        except ValidationError as e:
            return Response({'detail': str(e.detail)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserCouponSerializer(uc).data)


# ========== 优惠预计算 ==========

class PromotionCalculateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        amount_str = request.query_params.get('amount', '').strip()
        coupon_id_str = request.query_params.get('coupon_id', '').strip()
        if not amount_str:
            return Response({'detail': '请传入 amount 参数。'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(amount_str)
        except Exception:
            return Response({'detail': 'amount 参数格式错误。'}, status=status.HTTP_400_BAD_REQUEST)
        coupon_id = int(coupon_id_str) if coupon_id_str else None
        result = PromotionEngine.calculate(request.user, amount, coupon_id)
        return Response(result.to_dict())

    def post(self, request):
        serializer = PromotionCalculateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = PromotionEngine.calculate(
            request.user,
            Decimal(data['amount']),
            data.get('coupon_id'),
        )
        return Response(result.to_dict())


# ========== 营销报表 ==========

class MarketingReportOverviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response(MarketingReportService.overall_summary())


class MarketingReportPromotionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        pid = request.query_params.get('promotion_id', '').strip()
        pid_int = int(pid) if pid else None
        return Response(MarketingReportService.promotion_summary(pid_int))


class MarketingReportCouponAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        cid = request.query_params.get('coupon_id', '').strip()
        cid_int = int(cid) if cid else None
        return Response(MarketingReportService.coupon_summary(cid_int))


# ========== 定时任务：优惠券过期扫描 ==========

class CouponExpireScanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        count = CouponService.mark_expired_coupons()
        return Response({'expired_count': count})
