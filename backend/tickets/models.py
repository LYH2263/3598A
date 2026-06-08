import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from housing.models import Room


def ticket_attachment_upload_path(instance, filename):
    ticket_id = instance.ticket_id or 'pending'
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f'{uuid.uuid4().hex}{ext}'
    return f'tickets/ticket_{ticket_id}/{new_filename}'


class Ticket(models.Model):
    CATEGORY_WATER = 'water'
    CATEGORY_ELECTRICITY = 'electricity'
    CATEGORY_NETWORK = 'network'
    CATEGORY_ACCOUNT = 'account'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_WATER, '水'),
        (CATEGORY_ELECTRICITY, '电'),
        (CATEGORY_NETWORK, '网络'),
        (CATEGORY_ACCOUNT, '账户'),
        (CATEGORY_OTHER, '其它'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, '低'),
        (PRIORITY_NORMAL, '普通'),
        (PRIORITY_HIGH, '高'),
        (PRIORITY_URGENT, '紧急'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_ASSIGNED = 'assigned'
    STATUS_PROCESSING = 'processing'
    STATUS_WAITING_CONFIRM = 'waiting_confirm'
    STATUS_COMPLETED = 'completed'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待派单'),
        (STATUS_ASSIGNED, '已派单'),
        (STATUS_PROCESSING, '处理中'),
        (STATUS_WAITING_CONFIRM, '待学生确认'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_CLOSED, '已关闭'),
    ]

    STATUS_TRANSITIONS = {
        STATUS_PENDING: [STATUS_ASSIGNED, STATUS_CLOSED],
        STATUS_ASSIGNED: [STATUS_PROCESSING, STATUS_PENDING, STATUS_CLOSED],
        STATUS_PROCESSING: [STATUS_WAITING_CONFIRM, STATUS_CLOSED],
        STATUS_WAITING_CONFIRM: [STATUS_COMPLETED, STATUS_PROCESSING, STATUS_CLOSED],
        STATUS_COMPLETED: [STATUS_CLOSED],
        STATUS_CLOSED: [],
    }

    title = models.CharField(max_length=200, verbose_name='工单标题')
    description = models.TextField(verbose_name='问题描述')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='类型')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL, verbose_name='紧急程度')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态')

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_tickets', verbose_name='提交学生')
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name='处理人',
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name='所在房间',
    )
    room_text = models.CharField(max_length=128, blank=True, default='', verbose_name='房间描述（手填）')

    contact_phone = models.CharField(max_length=20, blank=True, default='', verbose_name='联系电话')

    rating = models.IntegerField(null=True, blank=True, verbose_name='评分（1-5）')
    rating_comment = models.TextField(blank=True, default='', verbose_name='评价留言')
    rated_at = models.DateTimeField(null=True, blank=True, verbose_name='评价时间')

    sla_deadline = models.DateTimeField(null=True, blank=True, verbose_name='SLA截止时间')
    escalation_level = models.IntegerField(default=0, verbose_name='升级级别')

    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name='派单时间')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始处理时间')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'tickets'
        ordering = ['-created_at']
        verbose_name = '工单'
        verbose_name_plural = '工单'
        indexes = [
            models.Index(fields=['status', 'priority'], name='ticket_status_priority_idx'),
            models.Index(fields=['student', 'status'], name='ticket_student_status_idx'),
            models.Index(fields=['assignee', 'status'], name='ticket_assignee_status_idx'),
            models.Index(fields=['category', 'status'], name='ticket_category_status_idx'),
            models.Index(fields=['sla_deadline'], name='ticket_sla_deadline_idx'),
        ]

    def __str__(self) -> str:
        return f'#{self.id} {self.title}'

    @property
    def room_display(self) -> str:
        if self.room:
            return str(self.room)
        return self.room_text or '未指定'

    @property
    def is_sla_breached(self) -> bool:
        if not self.sla_deadline:
            return False
        return self.sla_deadline < timezone.now() and self.status not in (
            self.STATUS_COMPLETED, self.STATUS_CLOSED
        )

    def can_transition_to(self, target_status: str) -> bool:
        return target_status in self.STATUS_TRANSITIONS.get(self.status, [])


class TicketReply(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='replies', verbose_name='工单')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ticket_replies', verbose_name='回复人')
    content = models.TextField(verbose_name='回复内容')

    is_internal = models.BooleanField(default=False, verbose_name='是否内部备注')
    action_type = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='关联动作（status_change/assign等）',
    )
    action_detail = models.JSONField(default=dict, blank=True, verbose_name='动作详情')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ticket_replies'
        ordering = ['created_at']
        verbose_name = '工单回复'
        verbose_name_plural = '工单回复'
        indexes = [
            models.Index(fields=['ticket', 'created_at'], name='reply_ticket_created_idx'),
        ]

    def __str__(self) -> str:
        return f'Reply #{self.id} on Ticket #{self.ticket_id}'


class TicketAttachment(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='工单',
    )
    reply = models.ForeignKey(
        TicketReply,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachments',
        verbose_name='关联回复',
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='上传人')

    file = models.FileField(
        upload_to=ticket_attachment_upload_path,
        verbose_name='附件文件',
    )
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_size = models.IntegerField(default=0, verbose_name='文件大小（字节）')
    mime_type = models.CharField(max_length=128, blank=True, default='', verbose_name='MIME类型')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        db_table = 'ticket_attachments'
        ordering = ['-created_at']
        verbose_name = '工单附件'
        verbose_name_plural = '工单附件'

    def __str__(self) -> str:
        return self.file_name

    @property
    def file_url(self) -> str:
        if self.file:
            return self.file.url
        return ''


class TicketSLAConfig(models.Model):
    priority = models.CharField(
        max_length=20,
        choices=Ticket.PRIORITY_CHOICES,
        unique=True,
        verbose_name='优先级',
    )
    response_hours = models.IntegerField(default=4, verbose_name='响应时限（小时）')
    resolve_hours = models.IntegerField(default=24, verbose_name='解决时限（小时）')
    auto_escalate = models.BooleanField(default=True, verbose_name='是否自动升级')
    escalation_hours = models.IntegerField(default=2, verbose_name='超时后升级间隔（小时）')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ticket_sla_configs'
        verbose_name = '工单SLA配置'
        verbose_name_plural = '工单SLA配置'

    def __str__(self) -> str:
        return f'{self.get_priority_display()} - {self.response_hours}h/{self.resolve_hours}h'


class TicketEscalationLog(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='escalation_logs', verbose_name='工单')
    escalation_level = models.IntegerField(verbose_name='升级级别')
    from_status = models.CharField(max_length=20, verbose_name='原状态')
    reason = models.CharField(max_length=255, verbose_name='升级原因')
    notified_user_ids = models.JSONField(default=list, blank=True, verbose_name='已通知用户ID列表')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ticket_escalation_logs'
        ordering = ['-created_at']
        verbose_name = '工单升级日志'
        verbose_name_plural = '工单升级日志'

    def __str__(self) -> str:
        return f'Ticket #{self.ticket_id} Lv.{self.escalation_level}'
