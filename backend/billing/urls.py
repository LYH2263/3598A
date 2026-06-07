from django.urls import path

from billing.views import (
    ConsumptionListCreateAPIView,
    ConsumptionStatsAPIView,
    CrossMonthAdjustAPIView,
    DashboardAPIView,
    MonthlyStatementAdminDetailAPIView,
    MonthlyStatementAdminListAPIView,
    RechargeListCreateAPIView,
    RechargeOrderBatchReviewAPIView,
    RechargeOrderListCreateAPIView,
    RechargeOrderReviewAPIView,
    ReconciliationAPIView,
    SettlementRunAPIView,
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
]
