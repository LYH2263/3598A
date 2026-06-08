import logging

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from notices.models import Announcement
from notices.services import NotificationService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '扫描已到定时发布时间但尚未推送的公告，执行全员推送'

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(f'[{now}] 开始扫描待发布公告...')

        pending = Announcement.objects.filter(
            is_active=True,
            published=False,
        ).filter(
            Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now)
        )

        count = pending.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('没有需要发布的待处理公告。'))
            return

        self.stdout.write(f'找到 {count} 条待发布公告，开始推送...')

        success_count = 0
        for announcement in pending:
            try:
                push_count = NotificationService.push_announcement(announcement)
                success_count += 1
                logger.info(
                    'Scheduled announcement published: id=%s, title=%s, pushed_users=%s',
                    announcement.id,
                    announcement.title,
                    push_count,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ 公告 #{announcement.id}「{announcement.title}」已推送给 {push_count} 位用户'
                    )
                )
            except Exception:
                logger.exception('Failed to publish scheduled announcement: id=%s', announcement.id)
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ 公告 #{announcement.id}「{announcement.title}」推送失败'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'扫描完成：成功 {success_count}/{count} 条公告已推送。'
            )
        )
