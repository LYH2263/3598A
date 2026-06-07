from django.contrib import admin

from billing.models import (
    BalanceChangeLog,
    ConsumptionRecord,
    MonthlyStatement,
    RechargeOrder,
    RechargeRecord,
    ReconciliationDiff,
    SettlementRun,
    Wallet,
)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'balance', 'is_frozen', 'updated_at')
    search_fields = ('user__username',)
    list_filter = ('is_frozen',)


@admin.register(RechargeOrder)
class RechargeOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_no', 'user', 'amount', 'channel', 'status', 'reviewer', 'created_at')
    search_fields = ('order_no', 'user__username')
    list_filter = ('status', 'channel')


@admin.register(RechargeRecord)
class RechargeRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'channel', 'operator', 'created_at')
    search_fields = ('user__username', 'operator', 'order__order_no')
    list_filter = ('channel',)


@admin.register(ConsumptionRecord)
class ConsumptionRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'usage', 'unit_price', 'cost_amount', 'created_at')
    search_fields = ('user__username', 'operator')
    list_filter = ('category',)


@admin.register(BalanceChangeLog)
class BalanceChangeLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'change_type',
        'amount_delta',
        'balance_before',
        'balance_after',
        'operator',
        'is_settled',
        'settlement_period',
        'created_at',
    )
    search_fields = ('user__username', 'operator', 'related_order_no', 'settlement_period')
    list_filter = ('change_type', 'is_settled', 'settlement_period')


@admin.register(MonthlyStatement)
class MonthlyStatementAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'period',
        'opening_balance',
        'closing_balance',
        'status',
        'generated_by',
        'created_at',
    )
    search_fields = ('user__username', 'period', 'generated_by')
    list_filter = ('status', 'period')


@admin.register(SettlementRun)
class SettlementRunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'period',
        'mode',
        'target_user_id',
        'status',
        'total_users',
        'success_count',
        'failed_count',
        'triggered_by',
        'started_at',
        'finished_at',
    )
    search_fields = ('period', 'triggered_by')
    list_filter = ('mode', 'status', 'period')


@admin.register(ReconciliationDiff)
class ReconciliationDiffAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'run_id',
        'user',
        'wallet_balance',
        'recalculated_balance',
        'difference',
        'created_at',
    )
    search_fields = ('run_id', 'user__username')
    list_filter = ('period',)
