from django.contrib.auth.models import User
from django.db import models
from django.db.models import UniqueConstraint


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_frozen = models.BooleanField(default=False)
    frozen_reason = models.CharField(max_length=255, blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'


class RechargeOrder(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待审核'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
    ]

    CHANNEL_ALIPAY = 'alipay'
    CHANNEL_WECHAT = 'wechat'
    CHANNEL_BANK = 'bank'

    CHANNEL_CHOICES = [
        (CHANNEL_ALIPAY, '支付宝'),
        (CHANNEL_WECHAT, '微信支付'),
        (CHANNEL_BANK, '银行卡'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recharge_orders')
    order_no = models.CharField(max_length=40, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    submit_remark = models.CharField(max_length=255, blank=True)
    review_remark = models.CharField(max_length=255, blank=True)
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_recharge_orders',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recharge_orders'
        ordering = ['-created_at']


class RechargeRecord(models.Model):
    CHANNEL_ALIPAY = 'alipay'
    CHANNEL_WECHAT = 'wechat'
    CHANNEL_BANK = 'bank'

    CHANNEL_CHOICES = [
        (CHANNEL_ALIPAY, '支付宝'),
        (CHANNEL_WECHAT, '微信支付'),
        (CHANNEL_BANK, '银行卡'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recharges')
    order = models.OneToOneField(
        RechargeOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recharge_record',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    operator = models.CharField(max_length=64)
    remark = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recharge_records'
        ordering = ['-created_at']


class ConsumptionRecord(models.Model):
    CATEGORY_WATER = 'water'
    CATEGORY_ELECTRICITY = 'electricity'

    CATEGORY_CHOICES = [
        (CATEGORY_WATER, '水费'),
        (CATEGORY_ELECTRICITY, '电费'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consumptions')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    usage = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2)
    meter_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    operator = models.CharField(max_length=64)
    remark = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'consumption_records'
        ordering = ['-created_at']


class BalanceChangeLog(models.Model):
    TYPE_RECHARGE = 'recharge'
    TYPE_CONSUMPTION = 'consumption'
    TYPE_FREEZE = 'freeze'
    TYPE_UNFREEZE = 'unfreeze'
    TYPE_ADJUST = 'adjust'
    TYPE_REFUND = 'refund'
    TYPE_CROSS_MONTH_ADJUST = 'cross_month_adjust'

    CHANGE_TYPE_CHOICES = [
        (TYPE_RECHARGE, '充值入账'),
        (TYPE_CONSUMPTION, '消费扣费'),
        (TYPE_FREEZE, '账户冻结'),
        (TYPE_UNFREEZE, '账户解冻'),
        (TYPE_ADJUST, '余额调整'),
        (TYPE_REFUND, '退款'),
        (TYPE_CROSS_MONTH_ADJUST, '跨月调整'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='balance_logs')
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='change_logs')
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPE_CHOICES)
    amount_delta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    related_order_no = models.CharField(max_length=40, blank=True)
    operator = models.CharField(max_length=64)
    remark = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    is_settled = models.BooleanField(default=False, db_index=True)
    settlement_period = models.CharField(max_length=7, blank=True, default='', db_index=True, help_text='所属账期 YYYY-MM')
    cross_month_adjust_from = models.CharField(max_length=7, blank=True, default='', help_text='跨月调整来源账期 YYYY-MM')

    class Meta:
        db_table = 'balance_change_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'settlement_period']),
        ]


class MonthlyStatement(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ROLLED_BACK = 'rolled_back'

    STATUS_CHOICES = [
        (STATUS_DRAFT, '草稿'),
        (STATUS_PUBLISHED, '已发布'),
        (STATUS_ROLLED_BACK, '已回滚'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_statements')
    period = models.CharField(max_length=7, db_index=True, help_text='账期 YYYY-MM')

    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recharge_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    water_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    electricity_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    adjust_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cross_month_adjust_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    recharge_count = models.IntegerField(default=0)
    water_count = models.IntegerField(default=0)
    electricity_count = models.IntegerField(default=0)
    refund_count = models.IntegerField(default=0)
    adjust_count = models.IntegerField(default=0)

    previous_statement = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_statement',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    closed_at = models.DateTimeField(null=True, blank=True)
    generated_by = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'monthly_statements'
        ordering = ['-period']
        constraints = [
            UniqueConstraint(fields=['user', 'period'], name='uniq_user_period_statement'),
        ]
        indexes = [
            models.Index(fields=['period', 'status']),
        ]

    def __str__(self) -> str:
        return f'{self.user.username} - {self.period}'


class SettlementRun(models.Model):
    MODE_MONTH = 'month'
    MODE_USER = 'user'

    MODE_CHOICES = [
        (MODE_MONTH, '按月跑批'),
        (MODE_USER, '按用户重跑'),
    ]

    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_RUNNING, '运行中'),
        (STATUS_SUCCESS, '成功'),
        (STATUS_FAILED, '失败'),
    ]

    period = models.CharField(max_length=7, db_index=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    target_user_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    total_users = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    message = models.TextField(blank=True, default='')
    triggered_by = models.CharField(max_length=64, blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'settlement_runs'
        ordering = ['-started_at']


class ReconciliationDiff(models.Model):
    run_id = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reconciliation_diffs')
    period = models.CharField(max_length=7, blank=True, default='')
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recalculated_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reconciliation_diffs'
        ordering = ['-created_at']
