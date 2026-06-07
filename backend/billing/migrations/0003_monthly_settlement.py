from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_order_freeze_logs'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='balancechangelog',
            name='change_type',
            field=models.CharField(
                choices=[
                    ('recharge', '充值入账'),
                    ('consumption', '消费扣费'),
                    ('freeze', '账户冻结'),
                    ('unfreeze', '账户解冻'),
                    ('adjust', '余额调整'),
                    ('refund', '退款'),
                    ('cross_month_adjust', '跨月调整'),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='balancechangelog',
            name='is_settled',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='balancechangelog',
            name='settlement_period',
            field=models.CharField(blank=True, db_index=True, default='', help_text='所属账期 YYYY-MM', max_length=7),
        ),
        migrations.AddField(
            model_name='balancechangelog',
            name='cross_month_adjust_from',
            field=models.CharField(blank=True, default='', help_text='跨月调整来源账期 YYYY-MM', max_length=7),
        ),
        migrations.AddIndex(
            model_name='balancechangelog',
            index=models.Index(fields=['user', 'settlement_period'], name='balance_change_user_settle_6b2e54_idx'),
        ),
        migrations.CreateModel(
            name='MonthlyStatement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.CharField(db_index=True, help_text='账期 YYYY-MM', max_length=7)),
                ('opening_balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('recharge_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('water_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('electricity_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('refund_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('adjust_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('cross_month_adjust_total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('closing_balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('recharge_count', models.IntegerField(default=0)),
                ('water_count', models.IntegerField(default=0)),
                ('electricity_count', models.IntegerField(default=0)),
                ('refund_count', models.IntegerField(default=0)),
                ('adjust_count', models.IntegerField(default=0)),
                ('status', models.CharField(
                    choices=[('draft', '草稿'), ('published', '已发布'), ('rolled_back', '已回滚')],
                    default='draft',
                    max_length=20,
                )),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('generated_by', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('previous_statement', models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='next_statement',
                    to='billing.monthlystatement',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monthly_statements',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'monthly_statements',
                'ordering': ['-period'],
                'constraints': [
                    models.UniqueConstraint(fields=['user', 'period'], name='uniq_user_period_statement'),
                ],
                'indexes': [
                    models.Index(fields=['period', 'status'], name='monthly_stmt_period_status_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='SettlementRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.CharField(db_index=True, max_length=7)),
                ('mode', models.CharField(choices=[('month', '按月跑批'), ('user', '按用户重跑')], max_length=20)),
                ('target_user_id', models.IntegerField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('running', '运行中'), ('success', '成功'), ('failed', '失败')],
                    default='running',
                    max_length=20,
                )),
                ('total_users', models.IntegerField(default=0)),
                ('success_count', models.IntegerField(default=0)),
                ('failed_count', models.IntegerField(default=0)),
                ('message', models.TextField(blank=True, default='')),
                ('triggered_by', models.CharField(blank=True, default='', max_length=64)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'settlement_runs',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='ReconciliationDiff',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('run_id', models.CharField(db_index=True, max_length=40)),
                ('period', models.CharField(blank=True, default='', max_length=7)),
                ('wallet_balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('recalculated_balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('difference', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reconciliation_diffs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'reconciliation_diffs',
                'ordering': ['-created_at'],
            },
        ),
    ]
