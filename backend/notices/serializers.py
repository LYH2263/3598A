from django.utils import timezone
from rest_framework import serializers

from notices.models import (
    Announcement,
    MessageDeliveryLog,
    MessageTemplate,
    MessageType,
    UserNotification,
    UserNotificationPreference,
)


class AnnouncementSerializer(serializers.ModelSerializer):
    publisher_name = serializers.CharField(source='publisher.username', read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(read_only=True)

    class Meta:
        model = Announcement
        fields = (
            'id', 'title', 'content', 'is_active', 'publisher_name',
            'published_at', 'scheduled_at', 'expires_at', 'published',
            'status', 'status_display',
        )


class AnnouncementCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    content = serializers.CharField(max_length=4000)
    is_active = serializers.BooleanField(default=True)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        scheduled_at = data.get('scheduled_at')
        expires_at = data.get('expires_at')
        if scheduled_at and expires_at and expires_at <= scheduled_at:
            raise serializers.ValidationError('失效时间必须晚于定时发布时间。')
        return data

    def create(self, validated_data):
        request = self.context['request']
        now = timezone.now()
        scheduled_at = validated_data.get('scheduled_at')
        should_publish_now = validated_data.get('is_active', True) and (
            scheduled_at is None or scheduled_at <= now
        )
        return Announcement.objects.create(
            title=validated_data['title'].strip(),
            content=validated_data['content'].strip(),
            is_active=validated_data.get('is_active', True),
            scheduled_at=scheduled_at,
            expires_at=validated_data.get('expires_at'),
            published=should_publish_now,
            publisher=request.user,
        )


class AnnouncementUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    content = serializers.CharField(max_length=4000, required=False)
    is_active = serializers.BooleanField(required=False)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        scheduled_at = data.get('scheduled_at', self.instance.scheduled_at if self.instance else None)
        expires_at = data.get('expires_at', self.instance.expires_at if self.instance else None)
        if scheduled_at and expires_at and expires_at <= scheduled_at:
            raise serializers.ValidationError('失效时间必须晚于定时发布时间。')
        return data

    def update(self, instance, validated_data):
        if 'title' in validated_data:
            instance.title = validated_data['title'].strip()
        if 'content' in validated_data:
            instance.content = validated_data['content'].strip()
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
        if 'scheduled_at' in validated_data:
            instance.scheduled_at = validated_data['scheduled_at']
        if 'expires_at' in validated_data:
            instance.expires_at = validated_data['expires_at']
        instance.save()
        return instance


class UserNotificationSerializer(serializers.ModelSerializer):
    notice_type_display = serializers.CharField(source='get_notice_type_display', read_only=True)

    class Meta:
        model = UserNotification
        fields = (
            'id',
            'title',
            'content',
            'notice_type',
            'notice_type_display',
            'is_read',
            'created_at',
            'read_at',
        )


class NotificationReadSerializer(serializers.Serializer):
    notification_id = serializers.IntegerField(required=False)
    mark_all = serializers.BooleanField(default=False)

    def save(self, **kwargs):
        request = self.context['request']
        mark_all = self.validated_data.get('mark_all', False)
        notification_id = self.validated_data.get('notification_id')

        queryset = UserNotification.objects.filter(user=request.user, is_read=False)
        if mark_all:
            updated = queryset.update(is_read=True, read_at=timezone.now())
            return {'updated_count': updated}

        notification = queryset.filter(id=notification_id).first()
        if not notification:
            raise serializers.ValidationError({'notification_id': '通知不存在或已读。'})

        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        return {'updated_count': 1}


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = (
            'id',
            'message_type',
            'language',
            'title_template',
            'content_template',
            'variables_schema',
            'is_active',
            'created_at',
            'updated_at',
        )


class MessageTypeSerializer(serializers.ModelSerializer):
    templates = MessageTemplateSerializer(many=True, read_only=True)
    channels_display = serializers.SerializerMethodField()

    class Meta:
        model = MessageType
        fields = (
            'id',
            'code',
            'name_zh',
            'name_en',
            'description_zh',
            'description_en',
            'category',
            'is_enabled',
            'default_channels',
            'channels_display',
            'quiet_hours_start',
            'quiet_hours_end',
            'templates',
            'created_at',
            'updated_at',
        )

    def get_channels_display(self, obj):
        label_map = dict(MessageType.CHANNEL_CHOICES)
        return [label_map.get(c, c) for c in obj.default_channels]


class MessageTypeCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageType
        fields = (
            'code',
            'name_zh',
            'name_en',
            'description_zh',
            'description_en',
            'category',
            'is_enabled',
            'default_channels',
            'quiet_hours_start',
            'quiet_hours_end',
        )


class MessageDeliveryLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)

    class Meta:
        model = MessageDeliveryLog
        fields = (
            'id',
            'event_id',
            'username',
            'user_id',
            'message_type_code',
            'channel',
            'channel_display',
            'status',
            'status_display',
            'rendered_title',
            'rendered_content',
            'variables',
            'language',
            'error_message',
            'retry_count',
            'sent_at',
            'created_at',
            'updated_at',
        )


class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    message_type_detail = MessageTypeSerializer(source='message_type', read_only=True)
    message_type_code = serializers.CharField(source='message_type.code', read_only=True)

    class Meta:
        model = UserNotificationPreference
        fields = (
            'id',
            'message_type',
            'message_type_code',
            'message_type_detail',
            'enabled_channels',
            'updated_at',
        )


class UserNotificationPreferenceWriteSerializer(serializers.Serializer):
    message_type_id = serializers.IntegerField()
    enabled_channels = serializers.ListField(child=serializers.CharField(max_length=20))

    def validate_enabled_channels(self, value):
        valid = {c[0] for c in MessageType.CHANNEL_CHOICES}
        for ch in value:
            if ch not in valid:
                raise serializers.ValidationError(f'非法渠道: {ch}')
        return value

    def save(self, **kwargs):
        request = self.context['request']
        mt_id = self.validated_data['message_type_id']
        channels = self.validated_data['enabled_channels']

        message_type = MessageType.objects.filter(id=mt_id).first()
        if not message_type:
            raise serializers.ValidationError({'message_type_id': '消息类型不存在。'})

        pref, _ = UserNotificationPreference.objects.update_or_create(
            user=request.user,
            message_type=message_type,
            defaults={'enabled_channels': channels},
        )
        return pref


class MessageTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = (
            'message_type',
            'language',
            'title_template',
            'content_template',
            'variables_schema',
            'is_active',
        )

    def validate(self, data):
        qs = MessageTemplate.objects.filter(
            message_type=data['message_type'],
            language=data['language'],
        )
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError('该语言模板已存在。')
        return data
