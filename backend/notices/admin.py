from django.contrib import admin

from notices.models import (
    Announcement,
    MessageDeliveryLog,
    MessageTemplate,
    MessageType,
    UserNotification,
    UserNotificationPreference,
)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status_display', 'is_active', 'published', 'publisher', 'published_at', 'scheduled_at', 'expires_at')
    search_fields = ('title', 'content')
    list_filter = ('is_active', 'published', 'scheduled_at', 'expires_at')
    readonly_fields = ('status_display',)

    def status_display(self, obj):
        return obj.status_display
    status_display.short_description = '状态'


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'notice_type', 'title', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'content')
    list_filter = ('notice_type', 'is_read')


@admin.register(MessageType)
class MessageTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_zh', 'category', 'is_enabled', 'default_channels', 'quiet_hours_start', 'quiet_hours_end')
    search_fields = ('code', 'name_zh', 'name_en')
    list_filter = ('is_enabled', 'category')


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('message_type', 'language', 'title_template', 'is_active')
    search_fields = ('message_type__code', 'title_template', 'content_template')
    list_filter = ('language', 'is_active')


@admin.register(MessageDeliveryLog)
class MessageDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'user', 'message_type_code', 'channel', 'status', 'sent_at', 'created_at')
    search_fields = ('event_id', 'user__username', 'message_type_code', 'rendered_title')
    list_filter = ('channel', 'status', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_type', 'enabled_channels', 'updated_at')
    search_fields = ('user__username', 'message_type__code')
