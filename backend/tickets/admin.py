from django.contrib import admin

from tickets.models import Ticket, TicketAttachment, TicketReply, TicketSLAConfig, TicketEscalationLog


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'priority', 'status', 'student', 'assignee', 'created_at')
    list_filter = ('status', 'category', 'priority')
    search_fields = ('title', 'description', 'student__username', 'assignee__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TicketReply)
class TicketReplyAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'author', 'created_at')
    search_fields = ('ticket__title', 'content')
    readonly_fields = ('created_at',)


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'file_name', 'uploaded_by', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(TicketSLAConfig)
class TicketSLAConfigAdmin(admin.ModelAdmin):
    list_display = ('priority', 'response_hours', 'resolve_hours', 'is_active')
    list_filter = ('priority', 'is_active')


@admin.register(TicketEscalationLog)
class TicketEscalationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'escalation_level', 'created_at')
    readonly_fields = ('created_at',)
