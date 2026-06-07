from django.contrib import admin

from marketing.models import (
    Coupon,
    Promotion,
    PromotionRedemption,
    UserCoupon,
    UserTag,
    UserTagRelation,
)


@admin.register(UserTag)
class UserTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'color', 'is_active', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(UserTagRelation)
class UserTagRelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'tag', 'created_at')
    search_fields = ('user__username', 'tag__name')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'promotion_type',
        'is_active',
        'start_time',
        'end_time',
        'audience_type',
        'limit_type',
        'limit_count',
        'stacking_policy',
        'created_by',
        'created_at',
    )
    search_fields = ('name', 'created_by__username')
    list_filter = ('promotion_type', 'is_active', 'audience_type', 'stacking_policy')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'coupon_type',
        'is_active',
        'scope',
        'face_value',
        'min_amount',
        'total_quantity',
        'issued_count',
        'per_user_limit',
        'valid_from',
        'valid_until',
        'created_by',
        'created_at',
    )
    search_fields = ('name', 'created_by__username')
    list_filter = ('coupon_type', 'is_active', 'scope')


@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'code',
        'user',
        'coupon',
        'status',
        'discount_amount',
        'used_at',
        'used_order_no',
        'expired_at',
        'granted_at',
    )
    search_fields = ('code', 'user__username', 'coupon__name', 'used_order_no')
    list_filter = ('status',)


@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'promotion',
        'order_no',
        'original_amount',
        'benefit_amount',
        'redemption_date',
        'created_at',
    )
    search_fields = ('user__username', 'promotion__name', 'order_no')
    list_filter = ('promotion__promotion_type', 'redemption_date')
