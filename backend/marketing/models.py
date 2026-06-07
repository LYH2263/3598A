from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models import UniqueConstraint


class UserTag(models.Model):
    name = models.CharField(max_length=64, unique=True, help_text='标签名称')
    description = models.CharField(max_length=255, blank=True, default='')
    color = models.CharField(max_length=16, blank=True, default='#409EFF', help_text='标签颜色')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mkt_user_tags'
        ordering = ['-id']

    def __str__(self) -> str:
        return self.name


class UserTagRelation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tag_relations')
    tag = models.ForeignKey(UserTag, on_delete=models.CASCADE, related_name='user_relations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mkt_user_tag_relations'
        constraints = [
            UniqueConstraint(fields=['user', 'tag'], name='uniq_user_tag'),
        ]


class Promotion(models.Model):
    TYPE_BONUS = 'bonus'
    TYPE_DISCOUNT = 'discount'
    TYPE_TIERED_CASHBACK = 'tiered_cashback'

    TYPE_CHOICES = [
        (TYPE_BONUS, '满赠（充X送Y）'),
        (TYPE_DISCOUNT, '满减（满A减B）'),
        (TYPE_TIERED_CASHBACK, '阶梯返现'),
    ]

    AUDIENCE_ALL = 'all'
    AUDIENCE_ROLE = 'role'
    AUDIENCE_TAG = 'tag'

    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, '全部用户'),
        (AUDIENCE_ROLE, '指定角色'),
        (AUDIENCE_TAG, '指定标签'),
    ]

    LIMIT_NONE = 'none'
    LIMIT_PER_DAY = 'per_day'
    LIMIT_TOTAL = 'total'

    LIMIT_CHOICES = [
        (LIMIT_NONE, '不限次'),
        (LIMIT_PER_DAY, '每人每日限享'),
        (LIMIT_TOTAL, '每人累计限享'),
    ]

    STACK_ALLOW = 'allow'
    STACK_EXCLUSIVE = 'exclusive'
    STACK_COUPON_ONLY = 'coupon_only'
    STACK_PROMO_ONLY = 'promo_only'

    STACK_CHOICES = [
        (STACK_ALLOW, '活动+优惠券可叠加'),
        (STACK_EXCLUSIVE, '互斥（用了活动不能用券，反之亦然）'),
        (STACK_COUPON_ONLY, '仅允许用券，活动不生效'),
        (STACK_PROMO_ONLY, '仅允许活动，优惠券不生效'),
    ]

    name = models.CharField(max_length=128, help_text='活动名称')
    description = models.CharField(max_length=500, blank=True, default='')
    promotion_type = models.CharField(max_length=30, choices=TYPE_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    start_time = models.DateTimeField(help_text='生效开始时间')
    end_time = models.DateTimeField(help_text='生效结束时间')

    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    audience_roles = models.JSONField(default=list, blank=True, help_text='指定角色，如 ["student"]')
    audience_tag_ids = models.JSONField(default=list, blank=True, help_text='指定标签ID列表')

    limit_type = models.CharField(max_length=20, choices=LIMIT_CHOICES, default=LIMIT_NONE)
    limit_count = models.IntegerField(default=0, help_text='限享次数，0 表示不限制')

    stacking_policy = models.CharField(max_length=30, choices=STACK_CHOICES, default=STACK_ALLOW, help_text='叠加策略')

    rule_config = models.JSONField(default=dict, help_text='活动规则：满赠={threshold, bonus}, 满减={threshold, discount}, 阶梯返现={tiers: [{threshold, rate}]}')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_promotions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mkt_promotions'
        ordering = ['-id']

    def __str__(self) -> str:
        return f'{self.name}({self.get_promotion_type_display()})'


class Coupon(models.Model):
    TYPE_FIXED = 'fixed'
    TYPE_PERCENT = 'percent'

    TYPE_CHOICES = [
        (TYPE_FIXED, '固定面额'),
        (TYPE_PERCENT, '折扣券'),
    ]

    SCOPE_PUBLIC = 'public'
    SCOPE_DIRECTED = 'directed'

    SCOPE_CHOICES = [
        (SCOPE_PUBLIC, '公开领取'),
        (SCOPE_DIRECTED, '定向发放'),
    ]

    name = models.CharField(max_length=128, help_text='优惠券名称')
    description = models.CharField(max_length=500, blank=True, default='')
    coupon_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_FIXED)
    is_active = models.BooleanField(default=True, db_index=True)

    face_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='固定面额（元）')
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'), help_text='折扣率，0.80 表示 8 折')
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='最低使用门槛（元）')
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='折扣券最大优惠金额')

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_DIRECTED)
    total_quantity = models.IntegerField(default=0, help_text='发放总量，0 表示不限')
    issued_count = models.IntegerField(default=0, help_text='已发放数量')
    per_user_limit = models.IntegerField(default=1, help_text='每人限领数量')

    valid_from = models.DateTimeField(help_text='生效开始时间')
    valid_until = models.DateTimeField(help_text='过期时间')

    audience_tag_ids = models.JSONField(default=list, blank=True, help_text='领取门槛：指定标签，空表示不限')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_coupons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mkt_coupons'
        ordering = ['-id']

    def __str__(self) -> str:
        return f'{self.name}'


class UserCoupon(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_USED = 'used'
    STATUS_EXPIRED = 'expired'
    STATUS_REVOKED = 'revoked'

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, '可用'),
        (STATUS_USED, '已用'),
        (STATUS_EXPIRED, '已过期'),
        (STATUS_REVOKED, '已回收'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupons')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='user_instances')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE, db_index=True)

    code = models.CharField(max_length=40, unique=True, help_text='券码')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='实际核销优惠金额（核销时填入）')

    used_at = models.DateTimeField(null=True, blank=True)
    used_order_no = models.CharField(max_length=40, blank=True, default='')
    expired_at = models.DateTimeField(help_text='实际过期时间（冗余自 coupon.valid_until，便于单独续期）')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_coupons')
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'mkt_user_coupons'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status'], name='mkt_uc_user_status_idx'),
        ]


class PromotionRedemption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promotion_redemptions')
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='redemptions')
    order_no = models.CharField(max_length=40, blank=True, default='', db_index=True)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    benefit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='优惠/赠送金额')
    redemption_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mkt_promotion_redemptions'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['promotion', 'user', 'redemption_date'], name='mkt_pr_promo_user_date_idx'),
        ]
