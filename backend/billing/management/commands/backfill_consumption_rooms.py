from django.core.management.base import BaseCommand

from billing.models import ConsumptionRecord
from billing.services.ledger_service import LedgerService


class Command(BaseCommand):
    help = '回填消费记录的 room_fk：按学生入住记录推断并绑定房间'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='仅预览不实际更新',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='每批处理条数，默认 500',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            default=False,
            help='是否覆盖已存在的 room_fk（默认仅处理 room_fk 为空的记录）',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='仅处理指定用户',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        overwrite = options['overwrite']
        user_id = options.get('user_id')

        qs = ConsumptionRecord.objects.select_related('user').order_by('id')
        if not overwrite:
            qs = qs.filter(room_fk__isnull=True)
        if user_id:
            qs = qs.filter(user_id=user_id)

        total = qs.count()
        self.stdout.write(self.style.WARNING(f'待处理消费记录：{total} 条'))
        if total == 0:
            self.stdout.write(self.style.SUCCESS('没有需要处理的记录。'))
            return

        matched = 0
        unmatched = 0
        updated = 0

        offset = 0
        while offset < total:
            batch = list(qs[offset:offset + batch_size])
            offset += batch_size

            updates = []
            for record in batch:
                room = LedgerService._infer_room_for_user(record.user, at_date=record.created_at.date())
                if room:
                    matched += 1
                    if not dry_run:
                        record.room_fk = room
                        if not record.building:
                            record.building = room.floor.building.name
                        if not record.room:
                            record.room = room.room_no
                        updates.append(record)
                else:
                    unmatched += 1

            if updates and not dry_run:
                ConsumptionRecord.objects.bulk_update(
                    updates,
                    fields=['room_fk', 'building', 'room'],
                    batch_size=100,
                )
                updated += len(updates)

            self.stdout.write(
                f'进度 {min(offset, total)}/{total}，本批匹配 {len(updates)}，累计匹配 {matched}，未匹配 {unmatched}'
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'处理完成：总计 {total}，匹配 {matched}，未匹配 {unmatched}'))
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'实际更新 {updated} 条记录'))
        else:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际写入数据库'))
