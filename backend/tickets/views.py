import logging

from django.db.models import Q, Count
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from tickets.models import Ticket, TicketAttachment, TicketSLAConfig
from tickets.serializers import (
    AdminUserSerializer,
    TicketAssignSerializer,
    TicketAttachmentSerializer,
    TicketAttachmentUploadSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketRateSerializer,
    TicketReplyCreateSerializer,
    TicketReplySerializer,
    TicketSLAConfigSerializer,
    TicketSerializer,
    TicketStatsSerializer,
    TicketStatusActionSerializer,
)
from tickets.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


def _is_admin(request) -> bool:
    return IsAdminRole().has_permission(request, None)


class TicketListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _build_queryset(self, request):
        user = request.user
        role = getattr(user.profile, 'role', 'student')
        qs = Ticket.objects.select_related('student', 'assignee', 'room', 'room__floor', 'room__floor__building')

        status_param = request.query_params.get('status', '').strip()
        category = request.query_params.get('category', '').strip()
        priority = request.query_params.get('priority', '').strip()
        keyword = request.query_params.get('keyword', '').strip()
        building_id = request.query_params.get('building_id', '').strip()
        assignee_id = request.query_params.get('assignee_id', '').strip()
        student_id = request.query_params.get('student_id', '').strip()
        only_mine = request.query_params.get('only_mine', 'false') == 'true'

        if role == 'student' or only_mine:
            qs = qs.filter(Q(student=user) | Q(assignee=user))
        elif role == 'admin':
            if student_id:
                qs = qs.filter(student_id=student_id)
            if assignee_id:
                if assignee_id == 'unassigned':
                    qs = qs.filter(assignee__isnull=True)
                else:
                    qs = qs.filter(assignee_id=assignee_id)

        if status_param:
            status_list = status_param.split(',')
            qs = qs.filter(status__in=status_list)
        if category:
            qs = qs.filter(category=category)
        if priority:
            qs = qs.filter(priority=priority)
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword)
                | Q(description__icontains=keyword)
            )
        if building_id and building_id.isdigit():
            qs = qs.filter(room__floor__building_id=int(building_id))

        return qs.order_by('-created_at')

    def get(self, request):
        queryset = self._build_queryset(request)
        limit = int(request.query_params.get('limit', '100'))
        limit = min(max(limit, 1), 500)
        serializer = TicketSerializer(queryset[:limit], many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        role = getattr(request.user.profile, 'role', 'student')
        if role != 'student':
            return Response({'detail': '仅学生可创建工单。'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TicketCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        logger.info('Ticket #%s created by %s', ticket.id, request.user.username)
        return Response(
            TicketDetailSerializer(ticket, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class TicketDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_ticket(self, request, pk):
        ticket = Ticket.objects.filter(pk=pk).select_related(
            'student', 'assignee', 'room', 'room__floor', 'room__floor__building'
        ).first()
        if not ticket:
            return None
        role = getattr(request.user.profile, 'role', 'student')
        if role == 'admin':
            return ticket
        if ticket.student_id == request.user.id or ticket.assignee_id == request.user.id:
            return ticket
        return None

    def get(self, request, pk):
        ticket = self._get_ticket(request, pk)
        if not ticket:
            return Response({'detail': '工单不存在或无权限查看。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TicketDetailSerializer(ticket, context={'request': request}).data)


class TicketAssignAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        ticket = Ticket.objects.filter(pk=pk).first()
        if not ticket:
            return Response({'detail': '工单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TicketAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ticket = serializer.save(ticket=ticket, operator=request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketDetailSerializer(ticket, context={'request': request}).data)


class TicketStatusActionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        ticket = Ticket.objects.filter(pk=pk).first()
        if not ticket:
            return Response({'detail': '工单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        role = getattr(request.user.profile, 'role', 'student')
        serializer = TicketStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']

        if action in ('start_processing', 'request_confirmation', 'close'):
            if role != 'admin':
                return Response({'detail': '仅管理员可执行此操作。'}, status=status.HTTP_403_FORBIDDEN)
            if action == 'start_processing' and ticket.assignee_id and ticket.assignee_id != request.user.id:
                return Response({'detail': '仅被指派的处理人可开始处理。'}, status=status.HTTP_403_FORBIDDEN)
        elif action in ('student_confirm', 'student_reject'):
            if ticket.student_id != request.user.id:
                return Response({'detail': '仅提交工单的学生可确认。'}, status=status.HTTP_403_FORBIDDEN)

        try:
            ticket = serializer.save(ticket=ticket, operator=request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketDetailSerializer(ticket, context={'request': request}).data)


class TicketReplyCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        ticket = Ticket.objects.filter(pk=pk).first()
        if not ticket:
            return Response({'detail': '工单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        role = getattr(request.user.profile, 'role', 'student')
        if role == 'student' and ticket.student_id != request.user.id:
            return Response({'detail': '无权限回复此工单。'}, status=status.HTTP_403_FORBIDDEN)
        if role == 'admin' and ticket.assignee_id != request.user.id:
            pass

        serializer = TicketReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_internal = serializer.validated_data.get('is_internal', False)
        if is_internal and role != 'admin':
            return Response({'detail': '仅管理员可发布内部备注。'}, status=status.HTTP_403_FORBIDDEN)

        try:
            reply = serializer.save(ticket=ticket, author=request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TicketReplySerializer(reply, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class TicketRateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        ticket = Ticket.objects.filter(pk=pk).first()
        if not ticket:
            return Response({'detail': '工单不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if ticket.student_id != request.user.id:
            return Response({'detail': '仅提交工单的学生可评价。'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TicketRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ticket = serializer.save(ticket=ticket, student=request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketDetailSerializer(ticket, context={'request': request}).data)


class TicketStatsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user.profile, 'role', 'student')
        qs = Ticket.objects.all()

        if role == 'student':
            qs = qs.filter(student=request.user)
        elif role == 'admin':
            scope = request.query_params.get('scope', 'all')
            if scope == 'mine':
                qs = qs.filter(assignee=request.user)

        stats = qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status=Ticket.STATUS_PENDING)),
            assigned=Count('id', filter=Q(status=Ticket.STATUS_ASSIGNED)),
            processing=Count('id', filter=Q(status=Ticket.STATUS_PROCESSING)),
            waiting_confirm=Count('id', filter=Q(status=Ticket.STATUS_WAITING_CONFIRM)),
            completed=Count('id', filter=Q(status=Ticket.STATUS_COMPLETED)),
            closed=Count('id', filter=Q(status=Ticket.STATUS_CLOSED)),
        )
        sla_breached = qs.filter(
            status__in=[Ticket.STATUS_PENDING, Ticket.STATUS_ASSIGNED, Ticket.STATUS_PROCESSING, Ticket.STATUS_WAITING_CONFIRM],
            sla_deadline__isnull=False,
        ).count()
        stats['sla_breached'] = sla_breached
        serializer = TicketStatsSerializer(stats)
        return Response(serializer.data)


class TicketAssigneesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        users = TicketService.get_admin_users()
        return Response(AdminUserSerializer(users, many=True).data)


class TicketMyTodosAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user.profile, 'role', 'student')
        if role != 'admin':
            return Response({'detail': '仅管理员可查看待办工作台。'}, status=status.HTTP_403_FORBIDDEN)

        todo_statuses = [Ticket.STATUS_ASSIGNED, Ticket.STATUS_PROCESSING, Ticket.STATUS_WAITING_CONFIRM]
        qs = Ticket.objects.filter(
            assignee=request.user,
            status__in=todo_statuses,
        ).select_related('student', 'room', 'room__floor', 'room__floor__building').order_by('priority', '-created_at')

        limit = int(request.query_params.get('limit', '100'))
        limit = min(max(limit, 1), 500)
        return Response(TicketSerializer(qs[:limit], many=True, context={'request': request}).data)


class TicketPoolAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Ticket.objects.select_related('student', 'assignee', 'room', 'room__floor', 'room__floor__building')

        status_param = request.query_params.get('status', '').strip()
        category = request.query_params.get('category', '').strip()
        priority = request.query_params.get('priority', '').strip()
        building_id = request.query_params.get('building_id', '').strip()
        keyword = request.query_params.get('keyword', '').strip()
        show_unassigned = request.query_params.get('unassigned_only', 'false') == 'true'

        if status_param:
            status_list = status_param.split(',')
            qs = qs.filter(status__in=status_list)
        if category:
            qs = qs.filter(category=category)
        if priority:
            qs = qs.filter(priority=priority)
        if building_id and building_id.isdigit():
            qs = qs.filter(room__floor__building_id=int(building_id))
        if show_unassigned:
            qs = qs.filter(assignee__isnull=True)
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword)
                | Q(description__icontains=keyword)
                | Q(student__username__icontains=keyword)
            )

        qs = qs.order_by('-priority', 'sla_deadline', '-created_at')
        limit = int(request.query_params.get('limit', '200'))
        limit = min(max(limit, 1), 1000)
        return Response(TicketSerializer(qs[:limit], many=True, context={'request': request}).data)


class TicketSLAConfigListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = TicketSLAConfig.objects.filter(is_active=True).order_by('priority')
        return Response(TicketSLAConfigSerializer(qs, many=True).data)


class TicketSLACheckAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        count = TicketService.batch_check_sla()
        return Response({'checked_count': count, 'detail': f'完成 SLA 检查，已升级 {count} 个超时工单。'})


class TicketConstantsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'categories': [{'value': v, 'label': l} for v, l in Ticket.CATEGORY_CHOICES],
            'priorities': [{'value': v, 'label': l} for v, l in Ticket.PRIORITY_CHOICES],
            'statuses': [{'value': v, 'label': l} for v, l in Ticket.STATUS_CHOICES],
            'status_transitions': dict(Ticket.STATUS_TRANSITIONS),
        })


class TicketAttachmentUploadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = []

    def post(self, request):
        from rest_framework.parsers import MultiPartParser, FormParser
        self.parser_classes = [MultiPartParser, FormParser]
        serializer = TicketAttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket_id = serializer.validated_data.get('ticket_id')
        if ticket_id:
            ticket = Ticket.objects.filter(id=ticket_id).first()
            if not ticket:
                return Response({'detail': '工单不存在。'}, status=status.HTTP_404_NOT_FOUND)
            if ticket.student_id != request.user.id and not _is_admin(request) and ticket.assignee_id != request.user.id:
                return Response({'detail': '您无权上传该工单的附件。'}, status=status.HTTP_403_FORBIDDEN)
        att = TicketService.upload_attachment(
            uploaded_by=request.user,
            file=serializer.validated_data['file'],
            ticket_id=ticket_id,
        )
        return Response(TicketAttachmentSerializer(att).data, status=status.HTTP_201_CREATED)


class TicketAttachmentDeleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        att = TicketAttachment.objects.filter(id=pk).first()
        if not att:
            return Response({'detail': '附件不存在。'}, status=status.HTTP_404_NOT_FOUND)
        is_admin = _is_admin(request)
        if att.uploaded_by_id != request.user.id and not is_admin:
            return Response({'detail': '您无权删除该附件。'}, status=status.HTTP_403_FORBIDDEN)
        if att.reply_id or (att.ticket_id and not is_admin):
            if att.reply_id:
                return Response({'detail': '已关联回复的附件不可删除。'}, status=status.HTTP_400_BAD_REQUEST)
        TicketService.delete_attachment(attachment_id=pk, operator=request.user)
        return Response({'detail': '已删除。'}, status=status.HTTP_200_OK)
