from django.urls import path

from billing.views import (
    AdminPlanExecutionListAPIView,
    AdminRechargePlanListAPIView,
    BIBuildingRoomAPIView,
    BICategoryAPIView,
    BIChannelAPIView,
    BICompareAPIView,
    BIDimensionOptionsAPIView,
    BIExportCSVAPIView,
    BIOverviewAPIView,
    BITimePeriodAPIView,
    BITopStudentsAPIView,
    BITrendAPIView,
    ConsumptionListCreateAPIView,
    ConsumptionStatsAPIView,
    CrossMonthAdjustAPIView,
    DashboardAPIView,
    DashboardPreferenceDetailAPIView,
    DashboardPreferenceListAPIView,
    MonthlyStatementAdminDetailAPIView,
    MonthlyStatementAdminListAPIView,
    PlanUpcomingAPIView,
    PricePreviewAPIView,
    PriceStrategyDetailAPIView,
    PriceStrategyListCreateAPIView,
    RechargeListCreateAPIView,
    RechargeOrderBatchReviewAPIView,
    RechargeOrderListCreateAPIView,
    RechargeOrderReviewAPIView,
    ReconciliationAPIView,
    SettlementRunAPIView,
    StudentProfileAnalyticsAPIView,
    StudentRechargePlanDetailAPIView,
    StudentRechargePlanListAPIView,
    StudentStatementDetailAPIView,
    StudentStatementDownloadCSVAPIView,
    StudentStatementListAPIView,
    WalletActionAPIView,
    WalletLogListAPIView,
)

urlpatterns = [
    path('dashboard/', DashboardAPIView.as_view(), name='dashboard'),
    path('recharges/', RechargeListCreateAPIView.as_view(), name='recharges'),
    path('recharge-orders/', RechargeOrderListCreateAPIView.as_view(), name='recharge-orders'),
    path('recharge-orders/<int:order_id>/review/', RechargeOrderReviewAPIView.as_view(), name='recharge-order-review'),
    path('recharge-orders/batch-review/', RechargeOrderBatchReviewAPIView.as_view(), name='recharge-order-batch-review'),
    path('consumptions/', ConsumptionListCreateAPIView.as_view(), name='consumptions'),
    path('consumptions/stats/', ConsumptionStatsAPIView.as_view(), name='consumptions-stats'),
    path('wallets/<int:user_id>/action/', WalletActionAPIView.as_view(), name='wallet-action'),
    path('wallet-logs/', WalletLogListAPIView.as_view(), name='wallet-logs'),

    path('statements/', StudentStatementListAPIView.as_view(), name='student-statements'),
    path('statements/<str:period>/', StudentStatementDetailAPIView.as_view(), name='student-statement-detail'),
    path('statements/<str:period>/csv/', StudentStatementDownloadCSVAPIView.as_view(), name='student-statement-csv'),

    path('admin/statements/', MonthlyStatementAdminListAPIView.as_view(), name='admin-statements'),
    path('admin/statements/<int:statement_id>/', MonthlyStatementAdminDetailAPIView.as_view(), name='admin-statement-detail'),
    path('admin/settlement-runs/', SettlementRunAPIView.as_view(), name='admin-settlement-runs'),
    path('admin/reconciliation/', ReconciliationAPIView.as_view(), name='admin-reconciliation'),
    path('admin/cross-month-adjust/', CrossMonthAdjustAPIView.as_view(), name='admin-cross-month-adjust'),

    # ========= BI 分析接口 =========
    path('bi/overview/', BIOverviewAPIView.as_view(), name='bi-overview'),
    path('bi/category/', BICategoryAPIView.as_view(), name='bi-category'),
    path('bi/trend/', BITrendAPIView.as_view(), name='bi-trend'),
    path('bi/channel/', BIChannelAPIView.as_view(), name='bi-channel'),
    path('bi/top-students/', BITopStudentsAPIView.as_view(), name='bi-top-students'),
    path('bi/building-room/', BIBuildingRoomAPIView.as_view(), name='bi-building-room'),
    path('bi/time-period/', BITimePeriodAPIView.as_view(), name='bi-time-period'),
    path('bi/compare/', BICompareAPIView.as_view(), name='bi-compare'),
    path('bi/dimensions/', BIDimensionOptionsAPIView.as_view(), name='bi-dimensions'),
    path('bi/export/<str:view_name>/', BIExportCSVAPIView.as_view(), name='bi-export'),

    # ========= 学生侧：我的分析 =========
    path('bi/my-profile/', StudentProfileAnalyticsAPIView.as_view(), name='bi-my-profile'),

    # ========= 看板偏好 =========
    path('dashboard-preferences/', DashboardPreferenceListAPIView.as_view(), name='dashboard-preferences-list'),
    path('dashboard-preferences/<str:board_key>/', DashboardPreferenceDetailAPIView.as_view(), name='dashboard-preferences-detail'),

    # ========= 学生侧：我的充值计划 =========
    path('plans/', StudentRechargePlanListAPIView.as_view(), name='student-plans'),
    path('plans/<int:plan_id>/', StudentRechargePlanDetailAPIView.as_view(), name='student-plan-detail'),
    path('plans/<int:plan_id>/<str:action>/', StudentRechargePlanDetailAPIView.as_view(), name='student-plan-action'),
    path('plans/upcoming/', PlanUpcomingAPIView.as_view(), name='plan-upcoming'),

    # ========= 管理员侧：充值计划管理 =========
    path('admin/plans/', AdminRechargePlanListAPIView.as_view(), name='admin-plans'),
    path('admin/plan-executions/', AdminPlanExecutionListAPIView.as_view(), name='admin-plan-executions'),

    # ========= 价格策略中心 =========
    path('pricing/strategies/', PriceStrategyListCreateAPIView.as_view(), name='pricing-strategies'),
    path('pricing/strategies/<int:strategy_id>/', PriceStrategyDetailAPIView.as_view(), name='pricing-strategy-detail'),
    path('pricing/preview/', PricePreviewAPIView.as_view(), name='pricing-preview'),
]
