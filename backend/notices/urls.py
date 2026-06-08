from django.urls import path

from notices.views import (
    AnnouncementDetailAPIView,
    AnnouncementListCreateAPIView,
    AnnouncementPublishAPIView,
    AnnouncementTakeOfflineAPIView,
    DeliveryLogExportAPIView,
    DeliveryLogListAPIView,
    DeliveryLogRetryAPIView,
    MessageTemplateDetailAPIView,
    MessageTemplateListCreateAPIView,
    MessageTypeDetailAPIView,
    MessageTypeListCreateAPIView,
    NotificationListAPIView,
    NotificationPreferenceBatchUpdateAPIView,
    NotificationPreferenceListAPIView,
    NotificationPreferenceUpdateAPIView,
    NotificationReadAPIView,
)

urlpatterns = [
    path('announcements/', AnnouncementListCreateAPIView.as_view(), name='announcements'),
    path('announcements/<int:pk>/', AnnouncementDetailAPIView.as_view(), name='announcement-detail'),
    path('announcements/<int:pk>/publish/', AnnouncementPublishAPIView.as_view(), name='announcement-publish'),
    path('announcements/<int:pk>/take-offline/', AnnouncementTakeOfflineAPIView.as_view(), name='announcement-take-offline'),
    path('notifications/', NotificationListAPIView.as_view(), name='notifications'),
    path('notifications/read/', NotificationReadAPIView.as_view(), name='notifications-read'),

    path('message-types/', MessageTypeListCreateAPIView.as_view(), name='message-types'),
    path('message-types/<int:pk>/', MessageTypeDetailAPIView.as_view(), name='message-types-detail'),

    path('message-templates/', MessageTemplateListCreateAPIView.as_view(), name='message-templates'),
    path('message-templates/<int:pk>/', MessageTemplateDetailAPIView.as_view(), name='message-templates-detail'),

    path('delivery-logs/', DeliveryLogListAPIView.as_view(), name='delivery-logs'),
    path('delivery-logs/export/', DeliveryLogExportAPIView.as_view(), name='delivery-logs-export'),
    path('delivery-logs/<int:log_id>/retry/', DeliveryLogRetryAPIView.as_view(), name='delivery-logs-retry'),

    path('notification-preferences/', NotificationPreferenceListAPIView.as_view(), name='notification-preferences'),
    path('notification-preferences/update/', NotificationPreferenceUpdateAPIView.as_view(), name='notification-preferences-update'),
    path('notification-preferences/batch/', NotificationPreferenceBatchUpdateAPIView.as_view(), name='notification-preferences-batch'),
]
