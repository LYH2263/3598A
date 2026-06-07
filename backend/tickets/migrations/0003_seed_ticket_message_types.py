from django.db import migrations


DEFAULT_MESSAGE_TYPES = [
    {
        'code': 'ticket_created',
        'name_zh': '新工单创建',
        'name_en': 'Ticket Created',
        'description_zh': '学生创建新工单时通知管理员',
        'description_en': 'Notify admins when student creates a new ticket',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '新工单 #{ticket_id}：{ticket_title}',
                'content_template': '新工单已创建，类型：{ticket_category}，优先级：{ticket_priority}，提交人：{student_name}。请及时处理。',
                'variables_schema': {'ticket_id': '工单ID', 'ticket_title': '工单标题', 'ticket_category': '类型', 'ticket_priority': '优先级', 'student_name': '学生'},
            },
            {
                'language': 'en',
                'title_template': 'New Ticket #{ticket_id}: {ticket_title}',
                'content_template': 'A new ticket has been created. Category: {ticket_category}, Priority: {ticket_priority}, Student: {student_name}.',
                'variables_schema': {'ticket_id': 'Ticket ID', 'ticket_title': 'Title', 'ticket_category': 'Category', 'ticket_priority': 'Priority', 'student_name': 'Student'},
            },
        ],
    },
    {
        'code': 'ticket_assigned',
        'name_zh': '工单已派单',
        'name_en': 'Ticket Assigned',
        'description_zh': '工单被指派给处理人时通知',
        'description_en': 'Notify when ticket is assigned to a handler',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id} 已派单',
                'content_template': '工单已指派给 {assignee_name} 处理。当前状态：{ticket_status}。',
                'variables_schema': {'ticket_id': '工单ID', 'assignee_name': '处理人', 'ticket_status': '状态'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id} Assigned',
                'content_template': 'Ticket has been assigned to {assignee_name}. Status: {ticket_status}.',
                'variables_schema': {'ticket_id': 'Ticket ID', 'assignee_name': 'Assignee', 'ticket_status': 'Status'},
            },
        ],
    },
    {
        'code': 'ticket_processing',
        'name_zh': '工单开始处理',
        'name_en': 'Ticket Processing',
        'description_zh': '处理人开始处理工单时通知',
        'description_en': 'Notify when handler starts processing the ticket',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id} 开始处理',
                'content_template': '您的工单正在处理中，请耐心等待。当前状态：{ticket_status}。',
                'variables_schema': {'ticket_id': '工单ID', 'ticket_status': '状态'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id} Processing',
                'content_template': 'Your ticket is now being processed. Status: {ticket_status}.',
                'variables_schema': {'ticket_id': 'Ticket ID', 'ticket_status': 'Status'},
            },
        ],
    },
    {
        'code': 'ticket_waiting_confirm',
        'name_zh': '工单待学生确认',
        'name_en': 'Ticket Waiting Confirmation',
        'description_zh': '处理完成等待学生确认时通知',
        'description_en': 'Notify student when ticket is resolved and awaiting confirmation',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id} 处理完成，待您确认',
                'content_template': '工单处理已完成，请确认是否解决。处理说明：{remark}',
                'variables_schema': {'ticket_id': '工单ID', 'remark': '处理说明'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id} Resolved, Awaiting Confirmation',
                'content_template': 'Ticket has been resolved, please confirm. Note: {remark}',
                'variables_schema': {'ticket_id': 'Ticket ID', 'remark': 'Remark'},
            },
        ],
    },
    {
        'code': 'ticket_confirmed',
        'name_zh': '工单学生确认结果',
        'name_en': 'Ticket Student Confirmation',
        'description_zh': '学生确认工单结果时通知处理人',
        'description_en': 'Notify handler of student confirmation result',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id}：学生确认结果',
                'content_template': '学生确认：{confirmed}。{reject_reason}',
                'variables_schema': {'ticket_id': '工单ID', 'confirmed': '是否确认', 'reject_reason': '拒绝原因'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id}: Student Confirmation',
                'content_template': 'Student confirmed: {confirmed}. {reject_reason}',
                'variables_schema': {'ticket_id': 'Ticket ID', 'confirmed': 'Confirmed', 'reject_reason': 'Reject Reason'},
            },
        ],
    },
    {
        'code': 'ticket_rated',
        'name_zh': '工单已评价',
        'name_en': 'Ticket Rated',
        'description_zh': '学生对工单完成评分评价时通知',
        'description_en': 'Notify when student rates the completed ticket',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id} 收到评价',
                'content_template': '学生评分：{rating} 星。评价：{comment}',
                'variables_schema': {'ticket_id': '工单ID', 'rating': '评分', 'comment': '评价'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id} Rated',
                'content_template': 'Student rating: {rating} stars. Comment: {comment}',
                'variables_schema': {'ticket_id': 'Ticket ID', 'rating': 'Rating', 'comment': 'Comment'},
            },
        ],
    },
    {
        'code': 'ticket_closed',
        'name_zh': '工单已关闭',
        'name_en': 'Ticket Closed',
        'description_zh': '工单被关闭时通知相关人员',
        'description_en': 'Notify related personnel when ticket is closed',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id} 已关闭',
                'content_template': '工单已关闭。原因：{reason}',
                'variables_schema': {'ticket_id': '工单ID', 'reason': '关闭原因'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id} Closed',
                'content_template': 'Ticket has been closed. Reason: {reason}',
                'variables_schema': {'ticket_id': 'Ticket ID', 'reason': 'Reason'},
            },
        ],
    },
    {
        'code': 'ticket_reply',
        'name_zh': '工单新回复',
        'name_en': 'Ticket Reply',
        'description_zh': '工单有新对话回复时通知',
        'description_en': 'Notify when there is a new reply on the ticket',
        'category': 'system',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '工单 #{ticket_id} 有新回复',
                'content_template': '{reply_author} 回复了工单：{reply_content}',
                'variables_schema': {'ticket_id': '工单ID', 'reply_author': '回复人', 'reply_content': '回复内容'},
            },
            {
                'language': 'en',
                'title_template': 'Ticket #{ticket_id} New Reply',
                'content_template': '{reply_author} replied: {reply_content}',
                'variables_schema': {'ticket_id': 'Ticket ID', 'reply_author': 'Author', 'reply_content': 'Content'},
            },
        ],
    },
    {
        'code': 'ticket_sla_breached',
        'name_zh': '工单SLA超时升级',
        'name_en': 'Ticket SLA Breached',
        'description_zh': '工单超时自动升级时通知管理员',
        'description_en': 'Notify admins when ticket SLA is breached and escalated',
        'category': 'security',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '【告警】工单 #{ticket_id} SLA 超时',
                'content_template': '工单处理超时，已自动升级至 Lv.{escalation_level}。请尽快处理。标题：{ticket_title}，优先级：{ticket_priority}，当前状态：{ticket_status}。',
                'variables_schema': {'ticket_id': '工单ID', 'escalation_level': '升级级别', 'ticket_title': '标题', 'ticket_priority': '优先级', 'ticket_status': '状态'},
            },
            {
                'language': 'en',
                'title_template': '[ALERT] Ticket #{ticket_id} SLA Breached',
                'content_template': 'Ticket processing timed out, auto-escalated to Lv.{escalation_level}. Please handle promptly. Title: {ticket_title}, Priority: {ticket_priority}, Status: {ticket_status}.',
                'variables_schema': {'ticket_id': 'Ticket ID', 'escalation_level': 'Escalation Level', 'ticket_title': 'Title', 'ticket_priority': 'Priority', 'ticket_status': 'Status'},
            },
        ],
    },
]


def seed_ticket_message_types(apps, schema_editor):
    MessageType = apps.get_model('notices', 'MessageType')
    MessageTemplate = apps.get_model('notices', 'MessageTemplate')

    for spec in DEFAULT_MESSAGE_TYPES:
        templates_spec = spec.pop('templates', [])
        mt, _ = MessageType.objects.update_or_create(
            code=spec['code'],
            defaults={k: v for k, v in spec.items() if k != 'templates'},
        )
        for tpl_spec in templates_spec:
            MessageTemplate.objects.update_or_create(
                message_type=mt,
                language=tpl_spec['language'],
                defaults={
                    'title_template': tpl_spec['title_template'],
                    'content_template': tpl_spec['content_template'],
                    'variables_schema': tpl_spec.get('variables_schema', {}),
                    'is_active': True,
                },
            )


def unseed_ticket_message_types(apps, schema_editor):
    MessageType = apps.get_model('notices', 'MessageType')
    MessageType.objects.filter(code__in=[s['code'] for s in DEFAULT_MESSAGE_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0002_seed_sla_configs'),
        ('notices', '0003_seed_default_message_types'),
    ]

    operations = [
        migrations.RunPython(seed_ticket_message_types, unseed_ticket_message_types),
    ]
