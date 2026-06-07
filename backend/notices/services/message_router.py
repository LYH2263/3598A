import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from notices.models import (
    MessageDeliveryLog,
    MessageTemplate,
    MessageType,
    UserNotificationPreference,
)
from notices.services.channel_sender import ChannelSenderFactory
from notices.services.template_engine import TemplateEngine

logger = logging.getLogger(__name__)


@dataclass
class MessageEvent:
    type_code: str
    user_ids: list[int]
    variables: dict[str, Any] = field(default_factory=dict)
    language: str = MessageTemplate.LANG_ZH
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: Any = field(default_factory=timezone.now)


class MessageRouter:
    @classmethod
    def dispatch_event(cls, event: MessageEvent) -> dict:
        from django.contrib.auth.models import User

        try:
            message_type = MessageType.objects.prefetch_related('templates').get(code=event.type_code)
        except MessageType.DoesNotExist:
            logger.error('MessageType not found: %s', event.type_code)
            return {'event_id': event.event_id, 'success': False, 'reason': 'message_type_not_found'}

        if not message_type.is_enabled:
            logger.info('MessageType disabled: %s', event.type_code)
            return {'event_id': event.event_id, 'success': False, 'reason': 'message_type_disabled'}

        template = TemplateEngine.get_template_for_language(message_type, event.language)
        if not template:
            logger.error('No active template for type=%s lang=%s', event.type_code, event.language)
            return {'event_id': event.event_id, 'success': False, 'reason': 'template_not_found'}

        rendered_title, rendered_content = TemplateEngine.render(template, event.variables)

        users = list(User.objects.filter(id__in=event.user_ids, is_active=True))
        if not users:
            return {'event_id': event.event_id, 'success': True, 'delivered': 0, 'users': 0}

        in_quiet = message_type.in_quiet_hours()
        logs_to_create = []

        for user in users:
            effective_channels = UserNotificationPreference.get_effective_channels(user, message_type)
            for channel in effective_channels:
                is_quiet_skip = (
                    in_quiet
                    and channel != MessageType.CHANNEL_IN_SITE
                )
                is_channel_skip = not effective_channels
                status = MessageDeliveryLog.STATUS_PENDING
                if is_quiet_skip:
                    status = MessageDeliveryLog.STATUS_QUIET
                elif is_channel_skip:
                    status = MessageDeliveryLog.STATUS_SKIPPED

                logs_to_create.append(MessageDeliveryLog(
                    event_id=event.event_id,
                    user=user,
                    message_type=message_type,
                    message_type_code=message_type.code,
                    channel=channel,
                    status=status,
                    rendered_title=rendered_title,
                    rendered_content=rendered_content,
                    variables=dict(event.variables),
                    language=event.language,
                ))

        created_logs = MessageDeliveryLog.objects.bulk_create(logs_to_create, batch_size=500)

        pending_logs = [log for log in created_logs if log.status == MessageDeliveryLog.STATUS_PENDING]
        for log in pending_logs:
            try:
                ChannelSenderFactory.dispatch(log)
            except Exception:
                logger.exception('Failed to dispatch log id=%s channel=%s', log.id, log.channel)

        success_count = sum(
            1 for log in created_logs
            if log.status == MessageDeliveryLog.STATUS_SUCCESS
        )
        return {
            'event_id': event.event_id,
            'success': True,
            'total_logs': len(created_logs),
            'success_count': success_count,
            'users': len(users),
        }

    @classmethod
    def retry_delivery(cls, log_id: int) -> MessageDeliveryLog:
        log = MessageDeliveryLog.objects.select_related('user', 'message_type').get(id=log_id)
        log.status = MessageDeliveryLog.STATUS_PENDING
        log.retry_count += 1
        log.error_message = ''
        log.save(update_fields=['status', 'retry_count', 'error_message', 'updated_at'])
        ChannelSenderFactory.dispatch(log)
        log.refresh_from_db()
        return log
