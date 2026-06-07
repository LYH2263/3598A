from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone


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

    coupon_id = models.IntegerField(null=True, blank=True, help_text='选择的用户优惠券ID')
    applied_promotions = models.JSONField(default=list, blank=True, help_text='命中的营销活动明细 [{promotion_id, name, type, benefit_amount}]')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='优惠券优惠金额')
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='活动赠送金额')
    stacking_policy = models.CharField(max_length=30, blank=True, default='', help_text='实际采用的叠加策略快照')
    final_payable = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='学生实付金额（冗余，便于展示）')
    final_credited = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='最终到账金额（amount + bonus_amount - discount_amount 按规则落地）')

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

    CHANNEL_MANUAL = 'manual'
    CHANNEL_IC_CARD = 'ic_card'
    CHANNEL_ONLINE = 'online'
    CHANNEL_METER = 'smart_meter'

    CHANNEL_CHOICES = [
        (CHANNEL_MANUAL, '人工录入'),
        (CHANNEL_IC_CARD, '校园IC卡'),
        (CHANNEL_ONLINE, '在线缴费'),
        (CHANNEL_METER, '智能电表'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consumptions')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default=CHANNEL_MANUAL, db_index=True)
    usage = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2)
    meter_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    building = models.CharField(max_length=64, blank=True, default='', db_index=True, help_text='楼栋（冗余）')
    room = models.CharField(max_length=32, blank=True, default='', db_index=True, help_text='房间号（冗余）')
    room_fk = models.ForeignKey(
        'housing.Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consumptions',
        help_text='关联房间',
    )
    operator = models.CharField(max_length=64)
    remark = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'consumption_records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'created_at'], name='consump_cat_created_idx'),
            models.Index(fields=['channel', 'created_at'], name='consump_chn_created_idx'),
            models.Index(fields=['user', 'category', 'created_at'], name='consump_user_cat_idx'),
        ]


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
            models.Index(fields=['user', 'settlement_period'], name='bcl_user_settlement_period_idx'),
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
            models.Index(fields=['period', 'status'], name='monthly_stmt_period_status_idx'),
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


class DashboardPreference(models.Model):
    BOARD_ADMIN_BI = 'admin_bi'
    BOARD_STUDENT_MY = 'student_my'

    BOARD_CHOICES = [
        (BOARD_ADMIN_BI, '管理员消费分析'),
        (BOARD_STUDENT_MY, '学生我的分析'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_preferences')
    board_key = models.CharField(max_length=40, choices=BOARD_CHOICES)
    card_order = models.JSONField(default=list, help_text='卡片ID顺序列表')
    collapsed_cards = models.JSONField(default=list, help_text='已折叠的卡片ID列表')
    filters_snapshot = models.JSONField(default=dict, blank=True, help_text='上次使用的筛选条件快照')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dashboard_preferences'
        constraints = [
            UniqueConstraint(fields=['user', 'board_key'], name='uniq_user_board_pref'),
        ]


class RechargePlan(models.Model):
    PERIOD_DAILY = 'daily'
    PERIOD_WEEKLY = 'weekly'
    PERIOD_MONTHLY = 'monthly'

    PERIOD_CHOICES = [
        (PERIOD_DAILY, '每日'),
        (PERIOD_WEEKLY, '每周'),
        (PERIOD_MONTHLY, '每月'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_ENDED = 'ended'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, '执行中'),
        (STATUS_PAUSED, '已暂停'),
        (STATUS_ENDED, '已结束'),
        (STATUS_EXPIRED, '已过期'),
    ]

    FAILURE_ACTION_SKIP = 'skip'
    FAILURE_ACTION_PAUSE = 'pause'

    FAILURE_ACTION_CHOICES = [
        (FAILURE_ACTION_SKIP, '跳过本次继续执行'),
        (FAILURE_ACTION_PAUSE, '暂停计划等待处理'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recharge_plans')
    name = models.CharField(max_length=100, help_text='计划名称')
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='每次充值金额')
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, help_text='扣款周期')
    channel = models.CharField(max_length=20, choices=RechargeOrder.CHANNEL_CHOICES, help_text='充值渠道')
    start_date = models.DateField(help_text='开始日期')
    end_date = models.DateField(help_text='结束日期')
    next_execution_date = models.DateField(db_index=True, help_text='下次执行日期')
    last_execution_date = models.DateField(null=True, blank=True, help_text='上次执行日期')
    total_executions = models.IntegerField(default=0, help_text='已执行次数')
    success_count = models.IntegerField(default=0, help_text='成功次数')
    failure_count = models.IntegerField(default=0, help_text='失败次数')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    failure_action = models.CharField(
        max_length=20,
        choices=FAILURE_ACTION_CHOICES,
        default=FAILURE_ACTION_SKIP,
        help_text='失败时处理策略',
    )
    created_by = models.CharField(max_length=64, default='student')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'recharge_plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='plan_user_status_idx'),
            models.Index(fields=['status', 'next_execution_date'], name='plan_status_next_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.user.username} - {self.name} ({self.get_period_display()})'

    def compute_next_execution_date(self, from_date=None) -> timezone.date:
        from_date = from_date or (self.last_execution_date or self.start_date)
        if self.period == self.PERIOD_DAILY:
            return from_date + timezone.timedelta(days=1)
        if self.period == self.PERIOD_WEEKLY:
            return from_date + timezone.timedelta(days=7)
        if self.period == self.PERIOD_MONTHLY:
            year = from_date.year
            month = from_date.month + 1
            if month > 12:
                month = 1
                year += 1
            day = min(from_date.day, 28)
            return timezone.datetime(year, month, day).date()
        return from_date


class PlanExecution(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_SUCCESS, '执行成功'),
        (STATUS_FAILED, '执行失败'),
        (STATUS_SKIPPED, '已跳过'),
    ]

    plan = models.ForeignKey(RechargePlan, on_delete=models.CASCADE, related_name='executions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plan_executions')
    scheduled_date = models.DateField(db_index=True, help_text='计划执行日期')
    executed_at = models.DateTimeField(null=True, blank=True, help_text='实际执行时间')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    order = models.OneToOneField(
        RechargeOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_execution',
        help_text='关联的充值订单',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='本次充值金额')
    channel = models.CharField(max_length=20, choices=RechargeOrder.CHANNEL_CHOICES)
    failure_reason = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'plan_executions'
        ordering = ['-scheduled_date', '-created_at']
        indexes = [
            models.Index(fields=['plan', 'scheduled_date'], name='exec_plan_date_idx'),
            models.Index(fields=['user', 'status'], name='exec_user_status_idx'),
        ]

    def __str__(self) -> str:
        return f'Plan#{self.plan_id} @ {self.scheduled_date} - {self.get_status_display()}'
