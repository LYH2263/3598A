from django.urls import path

from marketing.views import (
    CouponDetailAPIView,
    CouponExpireScanAPIView,
    CouponGrantAPIView,
    CouponListCreateAPIView,
    CouponPublicClaimAPIView,
    MarketingReportCouponAPIView,
    MarketingReportOverviewAPIView,
    MarketingReportPromotionAPIView,
    PromotionCalculateAPIView,
    PromotionDetailAPIView,
    PromotionListCreateAPIView,
    UserCouponAvailableForRechargeAPIView,
    UserCouponListAPIView,
    UserCouponRevokeAPIView,
    UserTagAssignAPIView,
    UserTagDetailAPIView,
    UserTagListCreateAPIView,
)

urlpatterns = [
    path('tags/', UserTagListCreateAPIView.as_view(), name='mkt-tags'),
    path('tags/<int:tag_id>/', UserTagDetailAPIView.as_view(), name='mkt-tag-detail'),
    path('tags/<int:tag_id>/<str:action>/', UserTagAssignAPIView.as_view(), name='mkt-tag-assign'),

    path('promotions/', PromotionListCreateAPIView.as_view(), name='mkt-promotions'),
    path('promotions/<int:promotion_id>/', PromotionDetailAPIView.as_view(), name='mkt-promotion-detail'),

    path('coupons/', CouponListCreateAPIView.as_view(), name='mkt-coupons'),
    path('coupons/<int:coupon_id>/', CouponDetailAPIView.as_view(), name='mkt-coupon-detail'),
    path('coupons/grant/', CouponGrantAPIView.as_view(), name='mkt-coupon-grant'),
    path('coupons/<int:coupon_id>/claim/', CouponPublicClaimAPIView.as_view(), name='mkt-coupon-claim'),
    path('coupons/scan-expire/', CouponExpireScanAPIView.as_view(), name='mkt-coupon-scan-expire'),

    path('user-coupons/', UserCouponListAPIView.as_view(), name='mkt-user-coupons'),
    path('user-coupons/available/', UserCouponAvailableForRechargeAPIView.as_view(), name='mkt-user-coupons-available'),
    path('user-coupons/<int:user_coupon_id>/revoke/', UserCouponRevokeAPIView.as_view(), name='mkt-user-coupon-revoke'),

    path('calculate/', PromotionCalculateAPIView.as_view(), name='mkt-calculate'),

    path('reports/overview/', MarketingReportOverviewAPIView.as_view(), name='mkt-report-overview'),
    path('reports/promotions/', MarketingReportPromotionAPIView.as_view(), name='mkt-report-promotions'),
    path('reports/coupons/', MarketingReportCouponAPIView.as_view(), name='mkt-report-coupons'),
]
