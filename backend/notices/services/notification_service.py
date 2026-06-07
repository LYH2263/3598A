from django.contrib.auth.models import User

from notices.models import Announcement, MessageTemplate, UserNotification
from notices.services.message_router import MessageEvent, MessageRouter


class NotificationService:
    @staticmethod
    def dispatch(type_code: str, user_ids: list[int], variables: dict | None = None, language: str = MessageTemplate.LANG_ZH):
        event = MessageEvent(
            type_code=type_code,
            user_ids=user_ids,
            variables=variables or {},
            language=language,
        )
        return MessageRouter.dispatch_event(event)

    @staticmethod
    def dispatch_for_user(type_code: str, user, variables: dict | None = None, language: str = MessageTemplate.LANG_ZH):
        return NotificationService.dispatch(
            type_code=type_code,
            user_ids=[user.id] if hasattr(user, 'id') else [int(user)],
            variables=variables or {},
            language=language,
        )

    @staticmethod
    def create_user_notification(user, title: str, content: str, notice_type: str = UserNotification.TYPE_SYSTEM, announcement=None):
        return UserNotification.objects.create(
            user=user,
            title=title,
            content=content,
            notice_type=notice_type,
            related_announcement=announcement,
        )

    @staticmethod
    def push_announcement(announcement):
        users = list(User.objects.filter(is_active=True).only('id'))
        if not users:
            return 0

        result = NotificationService.dispatch(
            type_code='announcement_published',
            user_ids=[u.id for u in users],
            variables={
                'title': announcement.title,
                'content': announcement.content,
            },
        )
        if result.get('success'):
            return result.get('users', 0)

        payloads = [
            UserNotification(
                user=user,
                title=f'系统公告：{announcement.title}',
                content=announcement.content,
                notice_type=UserNotification.TYPE_ANNOUNCEMENT,
                related_announcement=announcement,
            )
            for user in users
        ]
        UserNotification.objects.bulk_create(payloads, batch_size=500)
        return len(payloads)
