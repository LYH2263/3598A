from django.core.management.base import BaseCommand, CommandError

from billing.services.monthly_closing_service import MonthlyClosingService


class Command(BaseCommand):
    help = '执行财务月结：按月跑批/按用户重跑/账实校验'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            choices=['settle', 'reconcile'],
            default='settle',
            help='动作类型：settle 月结跑批，reconcile 账实校验',
        )
        parser.add_argument('--period', type=str, help='账期 YYYY-MM（settle 时必填）')
        parser.add_argument('--user-id', type=int, help='指定用户重跑（可选）')
        parser.add_argument(
            '--no-publish',
            action='store_true',
            help='生成草稿而非直接发布',
        )
        parser.add_argument(
            '--operator',
            type=str,
            default='system',
            help='操作人标识',
        )

    def handle(self, *args, **options):
        action = options['action']
        operator = options['operator']

        if action == 'settle':
            period = options['period']
            if not period:
                raise CommandError('--period 是必填参数。')
            user_id = options.get('user_id')
            auto_publish = not options['no_publish']

            self.stdout.write(
                f'开始月结跑批 period={period} user_id={user_id} auto_publish={auto_publish}'
            )
            run = MonthlyClosingService.run_monthly_settlement(
                period=period,
                operator=operator,
                auto_publish=auto_publish,
                user_id=user_id,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'完成 run_id={run.id} status={run.status} '
                    f'success={run.success_count} failed={run.failed_count}'
                )
            )
            if run.message:
                self.stdout.write(self.style.WARNING(f'错误明细:\n{run.message}'))

        elif action == 'reconcile':
            self.stdout.write('开始全平台账实校验...')
            result = MonthlyClosingService.run_reconciliation(operator=operator)
            self.stdout.write(
                self.style.SUCCESS(
                    f'校验完成 run_id={result["run_id"]} '
                    f'总用户={result["total_users"]} 差异用户={result["diff_count"]}'
                )
            )
            for d in result['diffs']:
                self.stdout.write(
                    f'  用户 {d["username"]}: 钱包={d["wallet_balance"]} '
                    f'重算={d["recalculated_balance"]} 差额={d["difference"]}'
                )
