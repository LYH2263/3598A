from django.core.management.base import BaseCommand

from tickets.services.ticket_service import TicketService


class Command(BaseCommand):
    help = '检查超时工单并执行SLA自动升级'

    def handle(self, *args, **options):
        self.stdout.write('开始SLA超时检查...')
        count = TicketService.batch_check_sla()
        self.stdout.write(self.style.SUCCESS(f'检查完成，已升级 {count} 个超时工单。'))
