from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_monthly_settlement'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='consumptionrecord',
            name='channel',
            field=models.CharField(
                choices=[
                    ('manual', '人工录入'),
                    ('ic_card', '校园IC卡'),
                    ('online', '在线缴费'),
                    ('smart_meter', '智能电表'),
                ],
                db_index=True,
                default='manual',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='consumptionrecord',
            name='building',
            field=models.CharField(blank=True, db_index=True, default='', help_text='楼栋', max_length=64),
        ),
        migrations.AddField(
            model_name='consumptionrecord',
            name='room',
            field=models.CharField(blank=True, db_index=True, default='', help_text='房间号', max_length=32),
        ),
        migrations.AlterField(
            model_name='consumptionrecord',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AddIndex(
            model_name='consumptionrecord',
            index=models.Index(fields=['category', 'created_at'], name='consumption_cat_created_9e3b62_idx'),
        ),
        migrations.AddIndex(
            model_name='consumptionrecord',
            index=models.Index(fields=['channel', 'created_at'], name='consumption_channel_created_1f0c7a_idx'),
        ),
        migrations.AddIndex(
            model_name='consumptionrecord',
            index=models.Index(fields=['user', 'category', 'created_at'], name='consumption_user_cat_5a2b91_idx'),
        ),
        migrations.CreateModel(
            name='DashboardPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('board_key', models.CharField(
                    choices=[('admin_bi', '管理员消费分析'), ('student_my', '学生我的分析')],
                    max_length=40,
                )),
                ('card_order', models.JSONField(default=list, help_text='卡片ID顺序列表')),
                ('collapsed_cards', models.JSONField(default=list, help_text='已折叠的卡片ID列表')),
                ('filters_snapshot', models.JSONField(blank=True, default=dict, help_text='上次使用的筛选条件快照')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dashboard_preferences',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'dashboard_preferences',
                'constraints': [
                    models.UniqueConstraint(fields=['user', 'board_key'], name='uniq_user_board_pref'),
                ],
            },
        ),
    ]
