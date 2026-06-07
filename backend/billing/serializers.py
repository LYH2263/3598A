from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import Profile
from billing.models import (
    BalanceChangeLog,
    ConsumptionRecord,
    DashboardPreference,
    MonthlyStatement,
    PlanExecution,
    RechargeOrder,
    RechargePlan,
    RechargeRecord,
    ReconciliationDiff,
    SettlementRun,
    Wallet,
)
from billing.services.ledger_service import LedgerService
from billing.services.recharge_plan_service import RechargePlanService


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ('balance', 'is_frozen', 'frozen_reason', 'frozen_at', 'updated_at')


class RechargeOrderSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.username', read_only=True)

    class Meta:
        model = RechargeOrder
        fields = (
            'id',
            'order_no',
            'user',
            'user_name',
            'amount',
            'channel',
            'status',
            'submit_remark',
            'review_remark',
            'reviewer_name',
            'reviewed_at',
            'created_at',
            'coupon_id',
            'applied_promotions',
            'discount_amount',
            'bonus_amount',
            'stacking_policy',
            'final_payable',
            'final_credited',
        )


class RechargeRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = RechargeRecord
        fields = (
            'id',
            'user',
            'user_name',
            'amount',
            'channel',
            'operator',
            'remark',
            'created_at',
            'order',
        )
        read_only_fields = ('id', 'user_name', 'operator', 'created_at')


class ConsumptionRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    room_id = serializers.IntegerField(source='room_fk_id', read_only=True, allow_null=True)
    building_name = serializers.CharField(source='room_fk.floor.building.name', read_only=True, allow_null=True)
    room_no = serializers.CharField(source='room_fk.room_no', read_only=True, allow_null=True)

    class Meta:
        model = ConsumptionRecord
        fields = (
            'id',
            'user',
            'user_name',
            'category',
            'category_display',
            'channel',
            'channel_display',
            'usage',
            'unit_price',
            'cost_amount',
            'meter_value',
            'building',
            'room',
            'room_id',
            'building_name',
            'room_no',
            'operator',
            'remark',
            'created_at',
        )
        read_only_fields = ('id', 'user_name', 'cost_amount', 'operator', 'created_at', 'category_display', 'channel_display', 'room_id', 'building_name', 'room_no')


class BalanceChangeLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)

    class Meta:
        model = BalanceChangeLog
        fields = (
            'id',
            'user',
            'user_name',
            'change_type',
            'change_type_display',
            'amount_delta',
            'balance_before',
            'balance_after',
            'related_order_no',
            'operator',
            'remark',
            'is_settled',
            'settlement_period',
            'cross_month_adjust_from',
            'created_at',
        )


class RechargeCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    channel = serializers.ChoiceField(choices=RechargeRecord.CHANNEL_CHOICES)
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context['request']
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)

        target_user = request.user
        if role == Profile.ROLE_ADMIN and attrs.get('user_id'):
            target_user = User.objects.filter(id=attrs['user_id']).first()
            if target_user is None:
                raise serializers.ValidationError({'user_id': '目标用户不存在。'})

        attrs['target_user'] = target_user
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        return LedgerService.create_recharge(
            user=validated_data['target_user'],
            amount=Decimal(validated_data['amount']),
            channel=validated_data['channel'],
            operator=request.user.username,
            remark=validated_data.get('remark', ''),
        )


class RechargeOrderCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    channel = serializers.ChoiceField(choices=RechargeOrder.CHANNEL_CHOICES)
    submit_remark = serializers.CharField(max_length=255, required=False, allow_blank=True)
    coupon_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    def create(self, validated_data):
        request = self.context['request']
        return LedgerService.create_recharge_order(
            user=request.user,
            amount=Decimal(validated_data['amount']),
            channel=validated_data['channel'],
            submit_remark=validated_data.get('submit_remark', ''),
            coupon_id=validated_data.get('coupon_id'),
        )


class RechargeOrderReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            (RechargeOrder.STATUS_APPROVED, '通过'),
            (RechargeOrder.STATUS_REJECTED, '驳回'),
        ]
    )
    review_remark = serializers.CharField(max_length=255, required=False, allow_blank=True)


class RechargeOrderBatchReviewSerializer(serializers.Serializer):
    MAX_BATCH_SIZE = 50

    order_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=MAX_BATCH_SIZE,
        error_messages={
            'min_length': '请至少选择一条订单。',
            'max_length': f'单次最多审核 {MAX_BATCH_SIZE} 条订单。',
        },
    )
    action = serializers.ChoiceField(
        choices=[
            (RechargeOrder.STATUS_APPROVED, '通过'),
            (RechargeOrder.STATUS_REJECTED, '驳回'),
        ]
    )
    review_remark = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_order_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('订单列表存在重复项。')
        return value


class ConsumptionCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    category = serializers.ChoiceField(choices=ConsumptionRecord.CATEGORY_CHOICES)
    channel = serializers.ChoiceField(choices=ConsumptionRecord.CHANNEL_CHOICES, required=False, default=ConsumptionRecord.CHANNEL_MANUAL)
    usage = serializers.DecimalField(max_digits=12, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    meter_value = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    building = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    room = serializers.CharField(max_length=32, required=False, allow_blank=True, default='')
    room_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context['request']
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)

        target_user = request.user
        if role == Profile.ROLE_ADMIN and attrs.get('user_id'):
            target_user = User.objects.filter(id=attrs['user_id']).first()
            if target_user is None:
                raise serializers.ValidationError({'user_id': '目标用户不存在。'})

        attrs['target_user'] = target_user
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        meter_value = validated_data.get('meter_value')
        meter_decimal = Decimal(meter_value) if meter_value is not None else None

        return LedgerService.create_consumption(
            user=validated_data['target_user'],
            category=validated_data['category'],
            channel=validated_data.get('channel', ConsumptionRecord.CHANNEL_MANUAL),
            usage=Decimal(validated_data['usage']),
            unit_price=Decimal(validated_data['unit_price']),
            meter_value=meter_decimal,
            building=validated_data.get('building', ''),
            room=validated_data.get('room', ''),
            room_id=validated_data.get('room_id'),
            operator=request.user.username,
            remark=validated_data.get('remark', ''),
        )


class WalletActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[('freeze', '冻结'), ('unfreeze', '解冻')])
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class MonthlyStatementSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_previous = serializers.SerializerMethodField()
    has_next = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyStatement
        fields = (
            'id',
            'user',
            'user_name',
            'period',
            'opening_balance',
            'recharge_total',
            'recharge_count',
            'water_total',
            'water_count',
            'electricity_total',
            'electricity_count',
            'refund_total',
            'refund_count',
            'adjust_total',
            'adjust_count',
            'cross_month_adjust_total',
            'closing_balance',
            'status',
            'status_display',
            'closed_at',
            'generated_by',
            'created_at',
            'updated_at',
            'has_previous',
            'has_next',
        )

    def get_has_previous(self, obj):
        return MonthlyStatement.objects.filter(
            user=obj.user, period__lt=obj.period
        ).exists()

    def get_has_next(self, obj):
        return MonthlyStatement.objects.filter(
            user=obj.user, period__gt=obj.period
        ).exists()


class SettlementRunSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = SettlementRun
        fields = (
            'id',
            'period',
            'mode',
            'mode_display',
            'target_user_id',
            'status',
            'status_display',
            'total_users',
            'success_count',
            'failed_count',
            'message',
            'triggered_by',
            'started_at',
            'finished_at',
        )


class RunSettlementSerializer(serializers.Serializer):
    period = serializers.RegexField(r'^\d{4}-\d{2}$', help_text='账期 YYYY-MM')
    auto_publish = serializers.BooleanField(default=True, required=False)
    user_id = serializers.IntegerField(required=False, allow_null=True)


class StatementActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[('publish', '发布'), ('rollback', '回滚')])


class CrossMonthAdjustSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    source_period = serializers.RegexField(r'^\d{4}-\d{2}$')
    target_period = serializers.RegexField(r'^\d{4}-\d{2}$')
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True)


class ReconciliationDiffSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ReconciliationDiff
        fields = (
            'id',
            'run_id',
            'user',
            'user_name',
            'period',
            'wallet_balance',
            'recalculated_balance',
            'difference',
            'detail',
            'created_at',
        )


class DashboardPreferenceSerializer(serializers.ModelSerializer):
    board_key_display = serializers.CharField(source='get_board_key_display', read_only=True)

    class Meta:
        model = DashboardPreference
        fields = (
            'id',
            'board_key',
            'board_key_display',
            'card_order',
            'collapsed_cards',
            'filters_snapshot',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'board_key_display', 'created_at', 'updated_at')


class DashboardPreferenceSaveSerializer(serializers.Serializer):
    board_key = serializers.ChoiceField(choices=DashboardPreference.BOARD_CHOICES)
    card_order = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    collapsed_cards = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    filters_snapshot = serializers.DictField(required=False, default=dict)


class BIFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    user_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=ConsumptionRecord.CATEGORY_CHOICES),
        required=False,
        default=list,
    )
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=ConsumptionRecord.CHANNEL_CHOICES),
        required=False,
        default=list,
    )
    min_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    max_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    buildings = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    rooms = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    trend_granularity = serializers.ChoiceField(
        choices=[('day', '日'), ('week', '周'), ('month', '月')],
        required=False,
        default='day',
    )
    top_n = serializers.IntegerField(min_value=1, max_value=100, required=False, default=10)


class BICompareSerializer(BIFilterSerializer):
    compare_start_date = serializers.DateField(required=False, allow_null=True)
    compare_end_date = serializers.DateField(required=False, allow_null=True)


class RechargePlanSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    failure_action_display = serializers.CharField(source='get_failure_action_display', read_only=True)
    countdown_days = serializers.SerializerMethodField()
    countdown_text = serializers.SerializerMethodField()

    class Meta:
        model = RechargePlan
        fields = (
            'id',
            'user',
            'user_name',
            'name',
            'amount',
            'period',
            'period_display',
            'channel',
            'channel_display',
            'start_date',
            'end_date',
            'next_execution_date',
            'last_execution_date',
            'total_executions',
            'success_count',
            'failure_count',
            'status',
            'status_display',
            'failure_action',
            'failure_action_display',
            'created_at',
            'updated_at',
            'paused_at',
            'ended_at',
            'end_reason',
            'countdown_days',
            'countdown_text',
        )
        read_only_fields = (
            'id', 'user', 'user_name', 'status_display', 'period_display',
            'channel_display', 'failure_action_display', 'created_at', 'updated_at',
            'paused_at', 'ended_at', 'end_reason', 'next_execution_date',
            'last_execution_date', 'total_executions', 'success_count', 'failure_count',
            'countdown_days', 'countdown_text',
        )

    def get_countdown_days(self, obj):
        from django.utils import timezone
        if obj.status != RechargePlan.STATUS_ACTIVE:
            return None
        today = timezone.now().date()
        delta = (obj.next_execution_date - today).days
        return delta

    def get_countdown_text(self, obj):
        from django.utils import timezone
        if obj.status != RechargePlan.STATUS_ACTIVE:
            return ''
        today = timezone.now().date()
        delta = (obj.next_execution_date - today).days
        if delta < 0:
            return '已过期'
        if delta == 0:
            return '今天执行'
        if delta == 1:
            return '明天执行'
        return f'{delta} 天后执行'


class RechargePlanCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    period = serializers.ChoiceField(choices=RechargePlan.PERIOD_CHOICES)
    channel = serializers.ChoiceField(choices=RechargeOrder.CHANNEL_CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    failure_action = serializers.ChoiceField(
        choices=RechargePlan.FAILURE_ACTION_CHOICES,
        required=False,
        default=RechargePlan.FAILURE_ACTION_SKIP,
    )

    def create(self, validated_data):
        request = self.context['request']
        return RechargePlanService.create_plan(
            user=request.user,
            name=validated_data.get('name', ''),
            amount=Decimal(validated_data['amount']),
            period=validated_data['period'],
            channel=validated_data['channel'],
            start_date=validated_data['start_date'],
            end_date=validated_data['end_date'],
            failure_action=validated_data.get('failure_action', RechargePlan.FAILURE_ACTION_SKIP),
        )


class PlanActionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class PlanExecutionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    order_no = serializers.CharField(source='order.order_no', read_only=True, allow_null=True)

    class Meta:
        model = PlanExecution
        fields = (
            'id',
            'plan',
            'plan_name',
            'user',
            'scheduled_date',
            'executed_at',
            'status',
            'status_display',
            'order',
            'order_no',
            'amount',
            'channel',
            'channel_display',
            'failure_reason',
            'created_at',
        )
        read_only_fields = fields
