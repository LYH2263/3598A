from django.db import migrations


DEFAULT_MESSAGE_TYPES = [
    {
        'code': 'order_approved',
        'name_zh': '充值订单审核通过',
        'name_en': 'Recharge Order Approved',
        'description_zh': '管理员审核通过充值订单时发送',
        'description_en': 'Sent when recharge order is approved by admin',
        'category': 'order',
        'default_channels': ['in_site', 'email'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '充值订单审核通过',
                'content_template': '订单 {order_no} 已审核通过，金额 ¥{amount} 已入账。',
                'variables_schema': {'order_no': '订单号', 'amount': '金额'},
            },
            {
                'language': 'en',
                'title_template': 'Recharge Order Approved',
                'content_template': 'Your order {order_no} has been approved. Amount ¥{amount} has been credited.',
                'variables_schema': {'order_no': 'Order No.', 'amount': 'Amount'},
            },
        ],
    },
    {
        'code': 'order_rejected',
        'name_zh': '充值订单被驳回',
        'name_en': 'Recharge Order Rejected',
        'description_zh': '管理员驳回充值订单时发送',
        'description_en': 'Sent when recharge order is rejected by admin',
        'category': 'order',
        'default_channels': ['in_site', 'email'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '充值订单被驳回',
                'content_template': '订单 {order_no} 已被驳回，请联系管理员。',
                'variables_schema': {'order_no': '订单号'},
            },
            {
                'language': 'en',
                'title_template': 'Recharge Order Rejected',
                'content_template': 'Your order {order_no} has been rejected. Please contact administrator.',
                'variables_schema': {'order_no': 'Order No.'},
            },
        ],
    },
    {
        'code': 'account_frozen',
        'name_zh': '账户已冻结',
        'name_en': 'Account Frozen',
        'description_zh': '管理员冻结用户账户时发送',
        'description_en': 'Sent when account is frozen by admin',
        'category': 'security',
        'default_channels': ['in_site', 'email', 'sms'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '账户已冻结',
                'content_template': '您的账户已被冻结，原因：{reason}。暂无法进行充值或消费，请联系管理员。',
                'variables_schema': {'reason': '冻结原因'},
            },
            {
                'language': 'en',
                'title_template': 'Account Frozen',
                'content_template': 'Your account has been frozen. Reason: {reason}. Please contact administrator.',
                'variables_schema': {'reason': 'Freeze reason'},
            },
        ],
    },
    {
        'code': 'account_unfrozen',
        'name_zh': '账户已解冻',
        'name_en': 'Account Unfrozen',
        'description_zh': '管理员解冻用户账户时发送',
        'description_en': 'Sent when account is unfrozen by admin',
        'category': 'security',
        'default_channels': ['in_site', 'email'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '账户已解冻',
                'content_template': '您的账户已解除冻结，可正常进行充值与消费。',
                'variables_schema': {},
            },
            {
                'language': 'en',
                'title_template': 'Account Unfrozen',
                'content_template': 'Your account has been unfrozen. You can recharge and consume normally.',
                'variables_schema': {},
            },
        ],
    },
    {
        'code': 'password_reset_code',
        'name_zh': '密码重置邮箱验证码',
        'name_en': 'Password Reset Code',
        'description_zh': '用户请求密码重置时发送验证码',
        'description_en': 'Sent with verification code when user requests password reset',
        'category': 'security',
        'default_channels': ['in_site', 'email'],
        'quiet_hours_start': None,
        'quiet_hours_end': None,
        'templates': [
            {
                'language': 'zh',
                'title_template': '密码重置邮箱验证码',
                'content_template': '您的密码重置验证码为：{code}，5分钟内有效。',
                'variables_schema': {'code': '验证码', 'masked_email': '脱敏邮箱'},
            },
            {
                'language': 'en',
                'title_template': 'Password Reset Code',
                'content_template': 'Your password reset code is: {code}. Valid for 5 minutes.',
                'variables_schema': {'code': 'Code', 'masked_email': 'Masked email'},
            },
        ],
    },
    {
        'code': 'password_changed',
        'name_zh': '密码变更提醒',
        'name_en': 'Password Changed',
        'description_zh': '用户密码成功重置后发送',
        'description_en': 'Sent after user password is successfully reset',
        'category': 'security',
        'default_channels': ['in_site', 'email'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '密码变更提醒',
                'content_template': '您的账号密码已重置。如果不是本人操作，请立即联系管理员。',
                'variables_schema': {},
            },
            {
                'language': 'en',
                'title_template': 'Password Changed',
                'content_template': 'Your account password has been reset. If this was not you, contact administrator immediately.',
                'variables_schema': {},
            },
        ],
    },
    {
        'code': 'account_updated',
        'name_zh': '账号状态变更提醒',
        'name_en': 'Account Status Updated',
        'description_zh': '管理员修改用户角色或启用状态时发送',
        'description_en': 'Sent when admin modifies user role or active status',
        'category': 'system',
        'default_channels': ['in_site', 'email'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '账号状态变更提醒',
                'content_template': '管理员已更新您的账号角色或启用状态。',
                'variables_schema': {},
            },
            {
                'language': 'en',
                'title_template': 'Account Status Updated',
                'content_template': 'Administrator has updated your account role or status.',
                'variables_schema': {},
            },
        ],
    },
    {
        'code': 'announcement_published',
        'name_zh': '系统公告发布',
        'name_en': 'Announcement Published',
        'description_zh': '管理员发布系统公告时发送给所有用户',
        'description_en': 'Sent to all users when admin publishes announcement',
        'category': 'announcement',
        'default_channels': ['in_site'],
        'templates': [
            {
                'language': 'zh',
                'title_template': '系统公告：{title}',
                'content_template': '{content}',
                'variables_schema': {'title': '公告标题', 'content': '公告内容'},
            },
            {
                'language': 'en',
                'title_template': 'Announcement: {title}',
                'content_template': '{content}',
                'variables_schema': {'title': 'Title', 'content': 'Content'},
            },
        ],
    },
]


def seed_message_types(apps, schema_editor):
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


def unseed_message_types(apps, schema_editor):
    MessageType = apps.get_model('notices', 'MessageType')
    MessageType.objects.filter(code__in=[s['code'] for s in DEFAULT_MESSAGE_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notices', '0002_message_center_models'),
    ]

    operations = [
        migrations.RunPython(seed_message_types, unseed_message_types),
    ]
