import csv
import io
import logging
from datetime import datetime

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from notices.models import (
    Announcement,
    MessageDeliveryLog,
    MessageTemplate,
    MessageType,
    UserNotification,
    UserNotificationPreference,
)
from notices.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    MessageDeliveryLogSerializer,
    MessageTemplateSerializer,
    MessageTemplateWriteSerializer,
    MessageTypeCreateUpdateSerializer,
    MessageTypeSerializer,
    NotificationReadSerializer,
    UserNotificationPreferenceSerializer,
    UserNotificationPreferenceWriteSerializer,
    UserNotificationSerializer,
)
from notices.services import MessageRouter, NotificationService

logger = logging.getLogger(__name__)


class AnnouncementListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        include_inactive = request.query_params.get('include_inactive', 'false') == 'true'
        is_admin = getattr(request.user.profile, 'role', 'student') == 'admin'
        queryset = Announcement.objects.all()

        if is_admin:
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
        else:
            now = timezone.now()
            queryset = queryset.filter(
                is_active=True,
                published=True,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            )

        return Response(AnnouncementSerializer(queryset[:100], many=True).data)

    def post(self, request):
        if not IsAdminRole().has_permission(request, self):
            return Response({'detail': IsAdminRole.message}, status=status.HTTP_403_FORBIDDEN)

        serializer = AnnouncementCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save()

        push_count = 0
        if announcement.published:
            push_count = NotificationService.push_announcement(announcement)
            logger.info('Announcement published by %s, pushed to %s users', request.user.username, push_count)
        else:
            logger.info(
                'Announcement scheduled by %s, scheduled_at=%s',
                request.user.username,
                announcement.scheduled_at,
            )

        return Response(
            {
                'announcement': AnnouncementSerializer(announcement).data,
                'push_count': push_count,
            },
            status=status.HTTP_201_CREATED,
        )


class NotificationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = UserNotification.objects.filter(user=request.user).order_by('-created_at')[:200]
        unread_count = UserNotification.objects.filter(user=request.user, is_read=False).count()
        return Response(
            {
                'unread_count': unread_count,
                'items': UserNotificationSerializer(queryset, many=True).data,
            }
        )


class NotificationReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = NotificationReadSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response({'detail': '通知状态已更新。', **result})


# ==================== 消息类型管理（管理员） ====================

class MessageTypeListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = MessageType.objects.prefetch_related('templates').all().order_by('code')
        return Response(MessageTypeSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = MessageTypeCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(MessageTypeSerializer(obj).data, status=status.HTTP_201_CREATED)


class MessageTypeDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        return MessageType.objects.prefetch_related('templates').filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({'detail': '消息类型不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MessageTypeSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({'detail': '消息类型不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MessageTypeCreateUpdateSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(MessageTypeSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({'detail': '消息类型不存在。'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== 消息模板管理（管理员） ====================

class MessageTemplateListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = MessageTemplate.objects.select_related('message_type').all().order_by('message_type__code', 'language')
        message_type_id = request.query_params.get('message_type_id', '').strip()
        if message_type_id:
            queryset = queryset.filter(message_type_id=message_type_id)
        return Response(MessageTemplateSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = MessageTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(MessageTemplateSerializer(obj).data, status=status.HTTP_201_CREATED)


class MessageTemplateDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        return MessageTemplate.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({'detail': '模板不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MessageTemplateSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({'detail': '模板不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MessageTemplateWriteSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(MessageTemplateSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({'detail': '模板不存在。'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== 发送日志（管理员） ====================

class DeliveryLogListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _build_queryset(self, request):
        queryset = MessageDeliveryLog.objects.select_related('user', 'message_type').all()
        message_type_code = request.query_params.get('message_type_code', '').strip()
        channel = request.query_params.get('channel', '').strip()
        status = request.query_params.get('status', '').strip()
        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        keyword = request.query_params.get('keyword', '').strip()

        if message_type_code:
            queryset = queryset.filter(message_type_code=message_type_code)
        if channel:
            queryset = queryset.filter(channel=channel)
        if status:
            queryset = queryset.filter(status=status)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if keyword:
            queryset = queryset.filter(
                Q(user__username__icontains=keyword)
                | Q(rendered_title__icontains=keyword)
                | Q(event_id__icontains=keyword)
            )
        return queryset.order_by('-created_at')

    def get(self, request):
        queryset = self._build_queryset(request)
        return Response(MessageDeliveryLogSerializer(queryset[:500], many=True).data)


class DeliveryLogExportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = MessageDeliveryLog.objects.select_related('user', 'message_type').all()
        message_type_code = request.query_params.get('message_type_code', '').strip()
        channel = request.query_params.get('channel', '').strip()
        status = request.query_params.get('status', '').strip()
        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()

        if message_type_code:
            queryset = queryset.filter(message_type_code=message_type_code)
        if channel:
            queryset = queryset.filter(channel=channel)
        if status:
            queryset = queryset.filter(status=status)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        queryset = queryset.order_by('-created_at')[:5000]

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['事件ID', '用户', '消息类型', '渠道', '状态', '标题', '发送时间', '创建时间', '错误信息', '重试次数'])
        status_map = dict(MessageDeliveryLog.STATUS_CHOICES)
        channel_map = dict(MessageType.CHANNEL_CHOICES)
        for log in queryset:
            writer.writerow([
                log.event_id,
                log.user.username,
                log.message_type_code,
                channel_map.get(log.channel, log.channel),
                status_map.get(log.status, log.status),
                log.rendered_title,
                log.sent_at.strftime('%Y-%m-%d %H:%M:%S') if log.sent_at else '',
                log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                log.error_message,
                log.retry_count,
            ])

        from django.http import HttpResponse
        response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="delivery_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return response


class DeliveryLogRetryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, log_id: int):
        log = MessageDeliveryLog.objects.filter(id=log_id).first()
        if not log:
            return Response({'detail': '日志不存在。'}, status=status.HTTP_404_NOT_FOUND)
        try:
            updated = MessageRouter.retry_delivery(log_id)
        except Exception as e:
            logger.exception('Retry delivery failed log_id=%s', log_id)
            return Response({'detail': f'重发失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(MessageDeliveryLogSerializer(updated).data)


# ==================== 用户通知偏好 ====================

class NotificationPreferenceListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        all_types = list(MessageType.objects.filter(is_enabled=True).prefetch_related('templates').order_by('code'))
        user_prefs = {
            p.message_type_id: p
            for p in UserNotificationPreference.objects.filter(user=request.user).select_related('message_type')
        }
        result = []
        for mt in all_types:
            pref = user_prefs.get(mt.id)
            result.append({
                'message_type': MessageTypeSerializer(mt).data,
                'enabled_channels': pref.enabled_channels if pref else list(mt.default_channels),
                'updated_at': pref.updated_at.isoformat() if pref else None,
            })
        return Response(result)


class NotificationPreferenceUpdateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserNotificationPreferenceWriteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        pref = serializer.save()
        return Response(UserNotificationPreferenceSerializer(pref).data)


class NotificationPreferenceBatchUpdateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get('items', [])
        if not isinstance(items, list):
            return Response({'detail': 'items 必须为数组。'}, status=status.HTTP_400_BAD_REQUEST)

        results = []
        errors = []
        for idx, item in enumerate(items):
            serializer = UserNotificationPreferenceWriteSerializer(data=item, context={'request': request})
            if serializer.is_valid():
                pref = serializer.save()
                results.append(UserNotificationPreferenceSerializer(pref).data)
            else:
                errors.append({'index': idx, 'errors': serializer.errors})

        return Response({
            'success_count': len(results),
            'items': results,
            'errors': errors,
        })
