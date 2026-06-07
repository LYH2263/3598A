from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0001_initial'),
        ('billing', '0004_bi_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='consumptionrecord',
            name='room_fk',
            field=models.ForeignKey(
                blank=True,
                help_text='关联房间',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='consumptions',
                to='housing.room',
            ),
        ),
        migrations.AlterField(
            model_name='consumptionrecord',
            name='building',
            field=models.CharField(blank=True, db_index=True, default='', help_text='楼栋（冗余）', max_length=64),
        ),
        migrations.AlterField(
            model_name='consumptionrecord',
            name='room',
            field=models.CharField(blank=True, db_index=True, default='', help_text='房间号（冗余）', max_length=32),
        ),
    ]
