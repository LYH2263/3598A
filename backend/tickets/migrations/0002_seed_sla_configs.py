from django.db import migrations


DEFAULT_SLA_CONFIGS = [
    {'priority': 'urgent', 'response_hours': 1, 'resolve_hours': 4, 'auto_escalate': True, 'escalation_hours': 1, 'is_active': True},
    {'priority': 'high', 'response_hours': 2, 'resolve_hours': 12, 'auto_escalate': True, 'escalation_hours': 2, 'is_active': True},
    {'priority': 'normal', 'response_hours': 4, 'resolve_hours': 24, 'auto_escalate': True, 'escalation_hours': 4, 'is_active': True},
    {'priority': 'low', 'response_hours': 8, 'resolve_hours': 72, 'auto_escalate': True, 'escalation_hours': 8, 'is_active': True},
]


def seed_sla_configs(apps, schema_editor):
    TicketSLAConfig = apps.get_model('tickets', 'TicketSLAConfig')
    for spec in DEFAULT_SLA_CONFIGS:
        TicketSLAConfig.objects.update_or_create(
            priority=spec['priority'],
            defaults=spec,
        )


def unseed_sla_configs(apps, schema_editor):
    TicketSLAConfig = apps.get_model('tickets', 'TicketSLAConfig')
    TicketSLAConfig.objects.filter(priority__in=[c['priority'] for c in DEFAULT_SLA_CONFIGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_sla_configs, unseed_sla_configs),
    ]
