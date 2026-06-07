import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    publisher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='published_announcements')
    published_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcements'
        ordering = ['-published_at']


class UserNotification(models.Model):
    TYPE_ANNOUNCEMENT = 'announcement'
    TYPE_ORDER = 'order'
    TYPE_SECURITY = 'security'
    TYPE_SYSTEM = 'system'

    TYPE_CHOICES = [
        (TYPE_ANNOUNCEMENT, '系统公告'),
        (TYPE_ORDER, '订单通知'),
        (TYPE_SECURITY, '安全通知'),
        (TYPE_SYSTEM, '系统消息'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    content = models.TextField()
    notice_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    is_read = models.BooleanField(default=False)
    related_announcement = models.ForeignKey(
        Announcement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
    )
    related_delivery_log = models.ForeignKey(
        'MessageDeliveryLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='site_notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_notifications'
        ordering = ['-created_at']


class MessageType(models.Model):
    CHANNEL_IN_SITE = 'in_site'
    CHANNEL_EMAIL = 'email'
    CHANNEL_SMS = 'sms'

    CHANNEL_CHOICES = [
        (CHANNEL_IN_SITE, '站内通知'),
        (CHANNEL_EMAIL, '邮件'),
        (CHANNEL_SMS, '短信'),
    ]

    NOTICE_TYPE_MAP = {
        'order': UserNotification.TYPE_ORDER,
        'security': UserNotification.TYPE_SECURITY,
        'system': UserNotification.TYPE_SYSTEM,
        'announcement': UserNotification.TYPE_ANNOUNCEMENT,
    }

    code = models.CharField(max_length=64, unique=True, help_text='消息类型唯一编码，如 order_approved')
    name_zh = models.CharField(max_length=128, help_text='中文名称')
    name_en = models.CharField(max_length=128, help_text='英文名称')
    description_zh = models.TextField(blank=True, default='', help_text='中文描述')
    description_en = models.TextField(blank=True, default='', help_text='英文描述')
    category = models.CharField(
        max_length=20,
        choices=UserNotification.TYPE_CHOICES,
        default=UserNotification.TYPE_SYSTEM,
        help_text='分类（映射到站内 notice_type）',
    )
    is_enabled = models.BooleanField(default=True, help_text='是否启用该消息类型')
    default_channels = models.JSONField(
        default=list,
        help_text='默认启用的渠道，如 ["in_site", "email"]',
    )
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text='静默时段开始（北京时间，如 22:00），该时段内不推送至邮箱/短信',
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text='静默时段结束（北京时间，如 08:00）',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message_types'
        ordering = ['code']

    def __str__(self) -> str:
        return f'{self.code} ({self.name_zh})'

    def clean(self):
        super().clean()
        if self.default_channels:
            valid_channels = {c[0] for c in self.CHANNEL_CHOICES}
            for ch in self.default_channels:
                if ch not in valid_channels:
                    raise ValidationError(f'非法渠道: {ch}')
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValidationError('静默时段开始和结束必须同时设置或同时为空')

    def in_quiet_hours(self, now=None) -> bool:
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        now = now or timezone.localtime(timezone.now()).time()
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end


class MessageTemplate(models.Model):
    LANG_ZH = 'zh'
    LANG_EN = 'en'

    LANGUAGE_CHOICES = [
        (LANG_ZH, '中文'),
        (LANG_EN, 'English'),
    ]

    message_type = models.ForeignKey(
        MessageType,
        on_delete=models.CASCADE,
        related_name='templates',
    )
    language = models.CharField(max_length=8, choices=LANGUAGE_CHOICES, default=LANG_ZH)
    title_template = models.CharField(max_length=255, help_text='标题模板，支持 {variable} 占位符')
    content_template = models.TextField(help_text='内容模板，支持 {variable} 占位符')
    variables_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text='变量说明 JSON，如 {"order_no": "订单号", "amount": "金额"}',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message_templates'
        unique_together = [('message_type', 'language')]
        ordering = ['message_type', 'language']

    def __str__(self) -> str:
        return f'{self.message_type.code} [{self.language}]'


class MessageDeliveryLog(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_QUIET = 'quiet'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待发送'),
        (STATUS_SUCCESS, '发送成功'),
        (STATUS_FAILED, '发送失败'),
        (STATUS_QUIET, '静默时段跳过'),
        (STATUS_SKIPPED, '用户偏好跳过'),
    ]

    event_id = models.CharField(max_length=64, db_index=True, help_text='同一次事件的所有渠道日志共享 event_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='message_delivery_logs')
    message_type = models.ForeignKey(
        MessageType,
        on_delete=models.SET_NULL,
        null=True,
        related_name='delivery_logs',
    )
    message_type_code = models.CharField(max_length=64, db_index=True)
    channel = models.CharField(max_length=20, choices=MessageType.CHANNEL_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    rendered_title = models.CharField(max_length=255, blank=True, default='')
    rendered_content = models.TextField(blank=True, default='')
    variables = models.JSONField(default=dict, blank=True)
    language = models.CharField(max_length=8, default=MessageTemplate.LANG_ZH)
    error_message = models.TextField(blank=True, default='')
    retry_count = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message_delivery_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'channel']),
        ]

    def __str__(self) -> str:
        return f'{self.event_id} | {self.user.username} | {self.channel} | {self.status}'


class UserNotificationPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_preferences')
    message_type = models.ForeignKey(MessageType, on_delete=models.CASCADE, related_name='user_preferences')
    enabled_channels = models.JSONField(
        default=list,
        help_text='用户启用的渠道，覆盖消息类型默认渠道',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_notification_preferences'
        unique_together = [('user', 'message_type')]

    def clean(self):
        super().clean()
        if self.enabled_channels:
            valid = {c[0] for c in MessageType.CHANNEL_CHOICES}
            for ch in self.enabled_channels:
                if ch not in valid:
                    raise ValidationError(f'非法渠道: {ch}')

    @classmethod
    def get_effective_channels(cls, user, message_type: MessageType) -> list:
        try:
            pref = cls.objects.get(user=user, message_type=message_type)
            return list(pref.enabled_channels)
        except cls.DoesNotExist:
            return list(message_type.default_channels)
