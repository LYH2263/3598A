from django.urls import path

from tickets.views import (
    TicketAssignAPIView,
    TicketAssigneesAPIView,
    TicketConstantsAPIView,
    TicketDetailAPIView,
    TicketListCreateAPIView,
    TicketMyTodosAPIView,
    TicketPoolAPIView,
    TicketRateAPIView,
    TicketReplyCreateAPIView,
    TicketSLACheckAPIView,
    TicketSLAConfigListAPIView,
    TicketStatsAPIView,
    TicketStatusActionAPIView,
)

urlpatterns = [
    path('', TicketListCreateAPIView.as_view(), name='ticket-list-create'),
    path('constants/', TicketConstantsAPIView.as_view(), name='ticket-constants'),
    path('stats/', TicketStatsAPIView.as_view(), name='ticket-stats'),
    path('pool/', TicketPoolAPIView.as_view(), name='ticket-pool'),
    path('my-todos/', TicketMyTodosAPIView.as_view(), name='ticket-my-todos'),
    path('assignees/', TicketAssigneesAPIView.as_view(), name='ticket-assignees'),
    path('sla-configs/', TicketSLAConfigListAPIView.as_view(), name='ticket-sla-configs'),
    path('sla-check/', TicketSLACheckAPIView.as_view(), name='ticket-sla-check'),
    path('<int:pk>/', TicketDetailAPIView.as_view(), name='ticket-detail'),
    path('<int:pk>/assign/', TicketAssignAPIView.as_view(), name='ticket-assign'),
    path('<int:pk>/action/', TicketStatusActionAPIView.as_view(), name='ticket-action'),
    path('<int:pk>/reply/', TicketReplyCreateAPIView.as_view(), name='ticket-reply'),
    path('<int:pk>/rate/', TicketRateAPIView.as_view(), name='ticket-rate'),
]
