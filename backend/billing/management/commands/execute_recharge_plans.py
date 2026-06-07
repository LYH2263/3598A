from django.core.management.base import BaseCommand

from billing.services.recharge_plan_service import RechargePlanService


class Command(BaseCommand):
    help = '扫描并执行到期的充值计划，自动生成充值订单进入审批流'

    def add_arguments(self, parser):
        parser.add_argument(
            '--operator',
            type=str,
            default='system',
            help='操作人标识',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅预览不实际执行',
        )

    def handle(self, *args, **options):
        operator = options['operator']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('[dry-run 模式：仅预览'))
            from billing.models import RechargePlan
            from django.utils import timezone
            today = timezone.now().date()
            due = RechargePlan.objects.filter(
                status=RechargePlan.STATUS_ACTIVE, next_execution_date__lte=today,
            ).count()
            self.stdout.write(f'即将执行的计划数: {due}')
            return

        self.stdout.write('开始执行到期充值计划...')
        result = RechargePlanService.execute_due_plans(operator=operator)
        self.stdout.write(
            self.style.SUCCESS(
                f'执行完成：总计={result["total"]} 成功={result["success"]} '
                f'失败={result["failed"]} 跳过={result["skipped"]} 到期标记过期={result["expired_count"]}'
            )
        )
        if result['errors']:
            self.stdout.write(self.style.WARNING('失败明细:'))
            for e in result['errors']:
                self.stdout.write(f'  plan_id={e["plan_id"]} 原因={e["reason"]}')
