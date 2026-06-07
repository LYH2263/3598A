from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('housing', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='工单标题')),
                ('description', models.TextField(verbose_name='问题描述')),
                ('category', models.CharField(choices=[('water', '水'), ('electricity', '电'), ('network', '网络'), ('account', '账户'), ('other', '其它')], max_length=20, verbose_name='类型')),
                ('priority', models.CharField(choices=[('low', '低'), ('normal', '普通'), ('high', '高'), ('urgent', '紧急')], default='normal', max_length=20, verbose_name='紧急程度')),
                ('status', models.CharField(choices=[('pending', '待派单'), ('assigned', '已派单'), ('processing', '处理中'), ('waiting_confirm', '待学生确认'), ('completed', '已完成'), ('closed', '已关闭')], default='pending', max_length=20, verbose_name='状态')),
                ('room_text', models.CharField(blank=True, default='', max_length=128, verbose_name='房间描述（手填）')),
                ('contact_phone', models.CharField(blank=True, default='', max_length=20, verbose_name='联系电话')),
                ('rating', models.IntegerField(blank=True, null=True, verbose_name='评分（1-5）')),
                ('rating_comment', models.TextField(blank=True, default='', verbose_name='评价留言')),
                ('rated_at', models.DateTimeField(blank=True, null=True, verbose_name='评价时间')),
                ('sla_deadline', models.DateTimeField(blank=True, null=True, verbose_name='SLA截止时间')),
                ('escalation_level', models.IntegerField(default=0, verbose_name='升级级别')),
                ('assigned_at', models.DateTimeField(blank=True, null=True, verbose_name='派单时间')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始处理时间')),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='解决时间')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='关闭时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tickets', to='auth.user', verbose_name='处理人')),
                ('room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tickets', to='housing.room', verbose_name='所在房间')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submitted_tickets', to='auth.user', verbose_name='提交学生')),
            ],
            options={
                'verbose_name': '工单',
                'verbose_name_plural': '工单',
                'db_table': 'tickets',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketSLAConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.CharField(choices=[('low', '低'), ('normal', '普通'), ('high', '高'), ('urgent', '紧急')], max_length=20, unique=True, verbose_name='优先级')),
                ('response_hours', models.IntegerField(default=4, verbose_name='响应时限（小时）')),
                ('resolve_hours', models.IntegerField(default=24, verbose_name='解决时限（小时）')),
                ('auto_escalate', models.BooleanField(default=True, verbose_name='是否自动升级')),
                ('escalation_hours', models.IntegerField(default=2, verbose_name='超时后升级间隔（小时）')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '工单SLA配置',
                'verbose_name_plural': '工单SLA配置',
                'db_table': 'ticket_sla_configs',
            },
        ),
        migrations.CreateModel(
            name='TicketReply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(verbose_name='回复内容')),
                ('is_internal', models.BooleanField(default=False, verbose_name='是否内部备注')),
                ('action_type', models.CharField(blank=True, default='', max_length=32, verbose_name='关联动作（status_change/assign等）')),
                ('action_detail', models.JSONField(blank=True, default=dict, verbose_name='动作详情')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ticket_replies', to='auth.user', verbose_name='回复人')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='tickets.ticket', verbose_name='工单')),
            ],
            options={
                'verbose_name': '工单回复',
                'verbose_name_plural': '工单回复',
                'db_table': 'ticket_replies',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketEscalationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('escalation_level', models.IntegerField(verbose_name='升级级别')),
                ('from_status', models.CharField(max_length=20, verbose_name='原状态')),
                ('reason', models.CharField(max_length=255, verbose_name='升级原因')),
                ('notified_user_ids', models.JSONField(blank=True, default=list, verbose_name='已通知用户ID列表')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='escalation_logs', to='tickets.ticket', verbose_name='工单')),
            ],
            options={
                'verbose_name': '工单升级日志',
                'verbose_name_plural': '工单升级日志',
                'db_table': 'ticket_escalation_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255, verbose_name='文件名')),
                ('file_url', models.URLField(max_length=512, verbose_name='文件URL')),
                ('file_size', models.IntegerField(default=0, verbose_name='文件大小（字节）')),
                ('mime_type', models.CharField(blank=True, default='', max_length=128, verbose_name='MIME类型')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('reply', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attachments', to='tickets.ticketreply', verbose_name='关联回复')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='tickets.ticket', verbose_name='工单')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='auth.user', verbose_name='上传人')),
            ],
            options={
                'verbose_name': '工单附件',
                'verbose_name_plural': '工单附件',
                'db_table': 'ticket_attachments',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='ticketreply',
            index=models.Index(fields=['ticket', 'created_at'], name='reply_ticket_created_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['status', 'priority'], name='ticket_status_priority_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['student', 'status'], name='ticket_student_status_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['assignee', 'status'], name='ticket_assignee_status_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['category', 'status'], name='ticket_category_status_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['sla_deadline'], name='ticket_sla_deadline_idx'),
        ),
    ]
