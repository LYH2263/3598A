from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import serializers

from marketing.models import (
    Coupon,
    Promotion,
    PromotionRedemption,
    UserCoupon,
    UserTag,
    UserTagRelation,
)


class UserTagSerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = UserTag
        fields = ('id', 'name', 'description', 'color', 'is_active', 'user_count', 'created_at')
        read_only_fields = ('id', 'created_at', 'user_count')

    def get_user_count(self, obj):
        return obj.user_relations.count()


class UserTagAssignSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField())


class PromotionSerializer(serializers.ModelSerializer):
    promotion_type_display = serializers.CharField(source='get_promotion_type_display', read_only=True)
    audience_type_display = serializers.CharField(source='get_audience_type_display', read_only=True)
    limit_type_display = serializers.CharField(source='get_limit_type_display', read_only=True)
    stacking_policy_display = serializers.CharField(source='get_stacking_policy_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = Promotion
        fields = (
            'id',
            'name',
            'description',
            'promotion_type',
            'promotion_type_display',
            'is_active',
            'start_time',
            'end_time',
            'audience_type',
            'audience_type_display',
            'audience_roles',
            'audience_tag_ids',
            'limit_type',
            'limit_type_display',
            'limit_count',
            'stacking_policy',
            'stacking_policy_display',
            'rule_config',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        ptype = attrs.get('promotion_type')
        cfg = attrs.get('rule_config') or {}
        if ptype == Promotion.TYPE_BONUS:
            if 'threshold' not in cfg or 'bonus' not in cfg:
                raise serializers.ValidationError({'rule_config': '满赠活动需要 threshold 和 bonus 字段'})
        elif ptype == Promotion.TYPE_DISCOUNT:
            if 'threshold' not in cfg or 'discount' not in cfg:
                raise serializers.ValidationError({'rule_config': '满减活动需要 threshold 和 discount 字段'})
        elif ptype == Promotion.TYPE_TIERED_CASHBACK:
            tiers = cfg.get('tiers')
            if not isinstance(tiers, list) or not tiers:
                raise serializers.ValidationError({'rule_config': '阶梯返现需要 tiers 数组'})
            for t in tiers:
                if 'threshold' not in t or 'rate' not in t:
                    raise serializers.ValidationError({'rule_config': '每个阶梯需要 threshold 和 rate'})
        if attrs.get('start_time') and attrs.get('end_time'):
            if attrs['start_time'] >= attrs['end_time']:
                raise serializers.ValidationError({'end_time': '结束时间必须晚于开始时间'})
        return attrs


class CouponSerializer(serializers.ModelSerializer):
    coupon_type_display = serializers.CharField(source='get_coupon_type_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    claimed_count = serializers.SerializerMethodField()
    used_count = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            'id',
            'name',
            'description',
            'coupon_type',
            'coupon_type_display',
            'is_active',
            'face_value',
            'discount_rate',
            'min_amount',
            'max_discount',
            'scope',
            'scope_display',
            'total_quantity',
            'issued_count',
            'per_user_limit',
            'valid_from',
            'valid_until',
            'audience_tag_ids',
            'created_by',
            'created_by_name',
            'claimed_count',
            'used_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'issued_count', 'created_at', 'updated_at', 'claimed_count', 'used_count')

    def get_claimed_count(self, obj):
        return obj.user_instances.count()

    def get_used_count(self, obj):
        return obj.user_instances.filter(status=UserCoupon.STATUS_USED).count()

    def validate(self, attrs):
        if attrs.get('valid_from') and attrs.get('valid_until'):
            if attrs['valid_from'] >= attrs['valid_until']:
                raise serializers.ValidationError({'valid_until': '过期时间必须晚于生效时间'})
        return attrs


class CouponGrantSerializer(serializers.Serializer):
    coupon_id = serializers.IntegerField()
    user_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    usernames = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class UserCouponSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    coupon_detail = serializers.SerializerMethodField()

    class Meta:
        model = UserCoupon
        fields = (
            'id',
            'code',
            'status',
            'status_display',
            'discount_amount',
            'used_at',
            'used_order_no',
            'expired_at',
            'granted_at',
            'revoked_at',
            'revoked_reason',
            'coupon',
            'coupon_detail',
        )
        read_only_fields = fields

    def get_coupon_detail(self, obj):
        c = obj.coupon
        return {
            'id': c.id,
            'name': c.name,
            'description': c.description,
            'coupon_type': c.coupon_type,
            'coupon_type_display': c.get_coupon_type_display(),
            'face_value': str(c.face_value),
            'discount_rate': str(c.discount_rate),
            'min_amount': str(c.min_amount),
            'max_discount': str(c.max_discount) if c.max_discount is not None else None,
            'valid_from': c.valid_from.isoformat() if c.valid_from else '',
            'valid_until': c.valid_until.isoformat() if c.valid_until else '',
        }


class PromotionCalculateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    coupon_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class CouponRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
