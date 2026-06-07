import logging

from django.utils import timezone

from notices.models import MessageDeliveryLog, MessageType, UserNotification

logger = logging.getLogger(__name__)


class BaseChannelSender:
    channel = None

    @classmethod
    def send(cls, log: MessageDeliveryLog) -> tuple[bool, str]:
        raise NotImplementedError


class InSiteChannelSender(BaseChannelSender):
    channel = MessageType.CHANNEL_IN_SITE

    @classmethod
    def send(cls, log: MessageDeliveryLog) -> tuple[bool, str]:
        try:
            notification = UserNotification.objects.create(
                user=log.user,
                title=log.rendered_title,
                content=log.rendered_content,
                notice_type=log.message_type.category if log.message_type else UserNotification.TYPE_SYSTEM,
                related_delivery_log=log,
            )
            log.site_notifications.add(notification)
            return True, f'站内通知创建成功 id={notification.id}'
        except Exception as e:
            logger.exception('InSiteChannelSender failed for log %s', log.id)
            return False, str(e)


class MockEmailChannelSender(BaseChannelSender):
    channel = MessageType.CHANNEL_EMAIL

    @classmethod
    def send(cls, log: MessageDeliveryLog) -> tuple[bool, str]:
        email = getattr(log.user, 'email', '') or 'unknown@demo.local'
        logger.info(
            '[MOCK EMAIL] To=%s Subject=%s Body=%s',
            email,
            log.rendered_title,
            log.rendered_content[:100],
        )
        return True, f'Mock 邮件已发送至 {email}'


class MockSmsChannelSender(BaseChannelSender):
    channel = MessageType.CHANNEL_SMS

    @classmethod
    def send(cls, log: MessageDeliveryLog) -> tuple[bool, str]:
        profile = getattr(log.user, 'profile', None)
        phone = getattr(profile, 'phone', '') or '138****0000'
        logger.info(
            '[MOCK SMS] To=%s Content=%s',
            phone,
            log.rendered_content[:200],
        )
        return True, f'Mock 短信已发送至 {phone}'


class ChannelSenderFactory:
    _senders = {
        MessageType.CHANNEL_IN_SITE: InSiteChannelSender,
        MessageType.CHANNEL_EMAIL: MockEmailChannelSender,
        MessageType.CHANNEL_SMS: MockSmsChannelSender,
    }

    @classmethod
    def get(cls, channel: str) -> BaseChannelSender | None:
        return cls._senders.get(channel)

    @classmethod
    def dispatch(cls, log: MessageDeliveryLog) -> None:
        sender = cls.get(log.channel)
        if not sender:
            log.status = MessageDeliveryLog.STATUS_FAILED
            log.error_message = f'未知渠道: {log.channel}'
            log.updated_at = timezone.now()
            log.save(update_fields=['status', 'error_message', 'updated_at'])
            return

        success, detail = sender.send(log)
        log.status = MessageDeliveryLog.STATUS_SUCCESS if success else MessageDeliveryLog.STATUS_FAILED
        log.error_message = '' if success else detail
        log.sent_at = timezone.now()
        log.updated_at = timezone.now()
        log.save(update_fields=['status', 'error_message', 'sent_at', 'updated_at'])
