from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notices', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usernotification',
            name='related_delivery_log',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='site_notifications',
                to='notices.messagedeliverylog',
            ),
        ),
        migrations.CreateModel(
            name='MessageType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='消息类型唯一编码，如 order_approved', max_length=64, unique=True)),
                ('name_zh', models.CharField(help_text='中文名称', max_length=128)),
                ('name_en', models.CharField(help_text='英文名称', max_length=128)),
                ('description_zh', models.TextField(blank=True, default='', help_text='中文描述')),
                ('description_en', models.TextField(blank=True, default='', help_text='英文描述')),
                ('category', models.CharField(
                    choices=[('announcement', '系统公告'), ('order', '订单通知'), ('security', '安全通知'), ('system', '系统消息')],
                    default='system',
                    help_text='分类（映射到站内 notice_type）',
                    max_length=20,
                )),
                ('is_enabled', models.BooleanField(default=True, help_text='是否启用该消息类型')),
                ('default_channels', models.JSONField(default=list, help_text='默认启用的渠道，如 ["in_site", "email"]')),
                ('quiet_hours_start', models.TimeField(blank=True, help_text='静默时段开始（北京时间，如 22:00），该时段内不推送至邮箱/短信', null=True)),
                ('quiet_hours_end', models.TimeField(blank=True, help_text='静默时段结束（北京时间，如 08:00）', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'message_types',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='MessageTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('zh', '中文'), ('en', 'English')], default='zh', max_length=8)),
                ('title_template', models.CharField(help_text='标题模板，支持 {variable} 占位符', max_length=255)),
                ('content_template', models.TextField(help_text='内容模板，支持 {variable} 占位符')),
                ('variables_schema', models.JSONField(blank=True, default=dict, help_text='变量说明 JSON')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='notices.messagetype')),
            ],
            options={
                'db_table': 'message_templates',
                'unique_together': {('message_type', 'language')},
                'ordering': ['message_type', 'language'],
            },
        ),
        migrations.CreateModel(
            name='MessageDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(db_index=True, help_text='同一次事件的所有渠道日志共享 event_id', max_length=64)),
                ('message_type_code', models.CharField(db_index=True, max_length=64)),
                ('channel', models.CharField(choices=[('in_site', '站内通知'), ('email', '邮件'), ('sms', '短信')], db_index=True, max_length=20)),
                ('status', models.CharField(
                    choices=[('pending', '待发送'), ('success', '发送成功'), ('failed', '发送失败'), ('quiet', '静默时段跳过'), ('skipped', '用户偏好跳过')],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('rendered_title', models.CharField(blank=True, default='', max_length=255)),
                ('rendered_content', models.TextField(blank=True, default='')),
                ('variables', models.JSONField(blank=True, default=dict)),
                ('language', models.CharField(default='zh', max_length=8)),
                ('error_message', models.TextField(blank=True, default='')),
                ('retry_count', models.IntegerField(default=0)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='delivery_logs', to='notices.messagetype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_delivery_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'message_delivery_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='messagedeliverylog',
            index=models.Index(fields=['created_at'], name='message_del_created_914234_idx'),
        ),
        migrations.AddIndex(
            model_name='messagedeliverylog',
            index=models.Index(fields=['status', 'channel'], name='message_del_status__7fbd4a_idx'),
        ),
        migrations.CreateModel(
            name='UserNotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled_channels', models.JSONField(default=list, help_text='用户启用的渠道，覆盖消息类型默认渠道')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_preferences', to='notices.messagetype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_notification_preferences',
                'unique_together': {('user', 'message_type')},
            },
        ),
        migrations.AlterField(
            model_name='usernotification',
            name='related_delivery_log',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='site_notifications',
                to='notices.messagedeliverylog',
            ),
        ),
    ]
