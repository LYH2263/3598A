from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.permissions import IsAdminRole
from housing.models import Room
from tickets.models import Ticket, TicketAttachment, TicketEscalationLog, TicketReply, TicketSLAConfig
from tickets.services.ticket_service import TicketService


def _is_admin(request):
    return IsAdminRole().has_permission(request, None)


class TicketAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = (
            'id',
            'ticket',
            'reply',
            'uploaded_by',
            'uploaded_by_name',
            'file_name',
            'file_url',
            'file_size',
            'mime_type',
            'created_at',
        )
        read_only_fields = ('id', 'ticket', 'reply', 'uploaded_by', 'uploaded_by_name', 'file_name', 'file_url', 'file_size', 'mime_type', 'created_at')

    def get_file_url(self, obj):
        return obj.file_url


class TicketAttachmentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    ticket_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate_file(self, value):
        allowed_mime = ['image/jpeg', 'image/png', 'image/jpg']
        allowed_ext = ['.jpg', '.jpeg', '.png']
        import os
        ext = os.path.splitext(value.name)[1].lower()
        if value.content_type and value.content_type not in allowed_mime:
            raise serializers.ValidationError('仅支持 JPG 和 PNG 格式图片。')
        if ext not in allowed_ext:
            raise serializers.ValidationError('仅支持 JPG 和 PNG 格式图片。')
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('图片大小不能超过 10MB。')
        return value


class TicketReplySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)
    author_role = serializers.SerializerMethodField()
    attachments = TicketAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TicketReply
        fields = (
            'id',
            'ticket',
            'author',
            'author_name',
            'author_role',
            'content',
            'is_internal',
            'action_type',
            'action_detail',
            'attachments',
            'created_at',
        )
        read_only_fields = ('id', 'ticket', 'author', 'author_name', 'author_role', 'attachments', 'created_at')

    def get_author_role(self, obj):
        profile = getattr(obj.author, 'profile', None)
        return profile.role if profile else 'student'


class TicketSLAConfigSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = TicketSLAConfig
        fields = (
            'id',
            'priority',
            'priority_display',
            'response_hours',
            'resolve_hours',
            'auto_escalate',
            'escalation_hours',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'priority_display', 'created_at', 'updated_at')


class TicketEscalationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketEscalationLog
        fields = (
            'id',
            'ticket',
            'escalation_level',
            'from_status',
            'reason',
            'notified_user_ids',
            'created_at',
        )
        read_only_fields = ('id', 'created_at')


class TicketSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    student_name = serializers.CharField(source='student.username', read_only=True)
    assignee_name = serializers.CharField(source='assignee.username', read_only=True, allow_null=True)

    room_id = serializers.IntegerField(source='room.id', read_only=True, allow_null=True)
    room_display = serializers.SerializerMethodField()

    reply_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    is_sla_breached = serializers.BooleanField(read_only=True)
    available_transitions = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            'id',
            'title',
            'description',
            'category',
            'category_display',
            'priority',
            'priority_display',
            'status',
            'status_display',

            'student',
            'student_name',
            'assignee',
            'assignee_name',

            'room_id',
            'room_display',
            'room_text',
            'contact_phone',

            'rating',
            'rating_comment',
            'rated_at',

            'sla_deadline',
            'is_sla_breached',
            'escalation_level',

            'assigned_at',
            'started_at',
            'resolved_at',
            'closed_at',
            'created_at',
            'updated_at',

            'reply_count',
            'attachment_count',
            'available_transitions',
        )
        read_only_fields = (
            'id',
            'status',
            'status_display',
            'student',
            'student_name',
            'assignee_name',
            'room_id',
            'room_display',
            'rating',
            'rating_comment',
            'rated_at',
            'sla_deadline',
            'is_sla_breached',
            'escalation_level',
            'assigned_at',
            'started_at',
            'resolved_at',
            'closed_at',
            'created_at',
            'updated_at',
            'reply_count',
            'attachment_count',
            'available_transitions',
        )

    def get_room_display(self, obj):
        return obj.room_display

    def get_reply_count(self, obj):
        return obj.replies.count()

    def get_attachment_count(self, obj):
        return obj.attachments.count()

    def get_available_transitions(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if not user:
            return []
        role = getattr(user.profile, 'role', 'student')
        transitions = list(Ticket.STATUS_TRANSITIONS.get(obj.status, []))

        if role != 'admin':
            allowed_for_student = []
            if obj.status == Ticket.STATUS_WAITING_CONFIRM:
                allowed_for_student = [Ticket.STATUS_COMPLETED, Ticket.STATUS_PROCESSING]
            transitions = [t for t in transitions if t in allowed_for_student]

        return transitions


class TicketDetailSerializer(TicketSerializer):
    replies = serializers.SerializerMethodField()
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    escalation_logs = TicketEscalationLogSerializer(many=True, read_only=True)

    class Meta(TicketSerializer.Meta):
        fields = TicketSerializer.Meta.fields + (
            'replies',
            'attachments',
            'escalation_logs',
        )

    def get_replies(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        role = getattr(user.profile, 'role', 'student') if user else 'student'
        qs = obj.replies.select_related('author', 'author__profile').order_by('created_at')
        if role != 'admin':
            qs = qs.filter(is_internal=False)
        return TicketReplySerializer(qs, many=True).data


class TicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=4000)
    category = serializers.ChoiceField(choices=Ticket.CATEGORY_CHOICES)
    priority = serializers.ChoiceField(choices=Ticket.PRIORITY_CHOICES, default=Ticket.PRIORITY_NORMAL)
    room_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    room_text = serializers.CharField(max_length=128, required=False, default='', allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )

    def validate_room_id(self, value):
        if value is None:
            return value
        room = Room.objects.filter(id=value, is_active=True).first()
        if not room:
            raise serializers.ValidationError('房间不存在或已停用。')
        return value

    def validate_attachment_ids(self, value):
        if not value:
            return value
        user = self.context['request'].user
        valid_ids = list(
            TicketAttachment.objects.filter(
                id__in=value,
                uploaded_by=user,
                ticket__isnull=True,
            ).values_list('id', flat=True)
        )
        invalid = set(value) - set(valid_ids)
        if invalid:
            raise serializers.ValidationError(f'附件 {sorted(invalid)} 不存在、不属于您或已被使用。')
        return value

    def create(self, validated_data):
        request = self.context['request']
        room_id = validated_data.pop('room_id', None)
        room = Room.objects.filter(id=room_id).first() if room_id else None
        attachment_ids = validated_data.pop('attachment_ids', [])
        return TicketService.create_ticket(
            student=request.user,
            title=validated_data['title'],
            description=validated_data['description'],
            category=validated_data['category'],
            priority=validated_data.get('priority', Ticket.PRIORITY_NORMAL),
            room=room,
            room_text=validated_data.get('room_text', ''),
            contact_phone=validated_data.get('contact_phone', ''),
            attachment_ids=attachment_ids,
        )


class TicketAssignSerializer(serializers.Serializer):
    assignee_id = serializers.IntegerField()

    def validate_assignee_id(self, value):
        user = User.objects.filter(id=value, is_active=True).select_related('profile').first()
        if not user:
            raise serializers.ValidationError('处理人不存在或已停用。')
        if getattr(user.profile, 'role', None) != 'admin':
            raise serializers.ValidationError('处理人必须为管理员角色。')
        return value

    def save(self, **kwargs):
        ticket = kwargs['ticket']
        operator = kwargs['operator']
        assignee = User.objects.get(id=self.validated_data['assignee_id'])
        return TicketService.assign_ticket(ticket=ticket, assignee=assignee, operator=operator)


class TicketStatusActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[
        'start_processing',
        'request_confirmation',
        'student_confirm',
        'student_reject',
        'close',
    ])
    remark = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)

    def save(self, **kwargs):
        ticket = kwargs['ticket']
        operator = kwargs['operator']
        action = self.validated_data['action']
        remark = self.validated_data.get('remark', '')

        if action == 'start_processing':
            return TicketService.start_processing(ticket, operator)
        elif action == 'request_confirmation':
            return TicketService.request_confirmation(ticket, operator, remark)
        elif action == 'student_confirm':
            return TicketService.student_confirm(ticket, operator, True, '')
        elif action == 'student_reject':
            return TicketService.student_confirm(ticket, operator, False, remark)
        elif action == 'close':
            return TicketService.close_ticket(ticket, operator, remark)
        raise serializers.ValidationError({'action': '无效的动作。'})


class TicketReplyCreateSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000)
    is_internal = serializers.BooleanField(default=False)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )

    def validate_attachment_ids(self, value):
        if not value:
            return value
        user = self.context['request'].user
        is_admin = _is_admin(self.context['request'])
        qs = TicketAttachment.objects.filter(id__in=value, uploaded_by=user, reply__isnull=True)
        if not is_admin:
            qs = qs.filter(is_internal=False) if hasattr(TicketAttachment, 'is_internal') else qs
        valid_ids = list(qs.values_list('id', flat=True))
        invalid = set(value) - set(valid_ids)
        if invalid:
            raise serializers.ValidationError(f'附件 {sorted(invalid)} 不存在、不属于您或已被使用。')
        return value

    def save(self, **kwargs):
        ticket = kwargs['ticket']
        author = kwargs['author']
        attachment_ids = self.validated_data.get('attachment_ids', [])
        return TicketService.add_reply(
            ticket=ticket,
            author=author,
            content=self.validated_data['content'],
            is_internal=self.validated_data.get('is_internal', False),
            attachment_ids=attachment_ids,
        )


class TicketRateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)

    def save(self, **kwargs):
        ticket = kwargs['ticket']
        student = kwargs['student']
        return TicketService.rate_ticket(
            ticket=ticket,
            student=student,
            rating=self.validated_data['rating'],
            comment=self.validated_data.get('comment', ''),
        )


class AdminUserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='profile.get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role_display')
        read_only_fields = ('id', 'username', 'email', 'role_display')


class TicketStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField(default=0)
    pending = serializers.IntegerField(default=0)
    assigned = serializers.IntegerField(default=0)
    processing = serializers.IntegerField(default=0)
    waiting_confirm = serializers.IntegerField(default=0)
    completed = serializers.IntegerField(default=0)
    closed = serializers.IntegerField(default=0)
    sla_breached = serializers.IntegerField(default=0)
