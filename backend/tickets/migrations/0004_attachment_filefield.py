from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0003_seed_ticket_message_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketattachment',
            name='file',
            field=models.FileField(upload_to='tickets/ticket_%7Bticket_id%7D/', verbose_name='附件文件'),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='ticketattachment',
            name='file_url',
        ),
    ]
