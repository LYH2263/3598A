from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Campus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='校区名称')),
                ('code', models.CharField(max_length=32, unique=True, verbose_name='校区编码')),
                ('address', models.CharField(blank=True, default='', max_length=255, verbose_name='地址')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'db_table': 'campus',
                'ordering': ['sort_order', 'id'],
                'verbose_name': '校区',
                'verbose_name_plural': '校区',
            },
        ),
        migrations.CreateModel(
            name='Building',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='楼栋名称')),
                ('code', models.CharField(max_length=32, verbose_name='楼栋编码')),
                ('building_type', models.CharField(
                    choices=[('dorm', '宿舍楼'), ('teaching', '教学楼'), ('office', '办公楼'), ('mixed', '综合楼')],
                    default='dorm',
                    max_length=20,
                    verbose_name='楼栋类型',
                )),
                ('gender_limit', models.CharField(
                    choices=[('male', '男生楼'), ('female', '女生楼'), ('mixed', '男女混合')],
                    default='mixed',
                    max_length=20,
                    verbose_name='性别限制',
                )),
                ('total_floors', models.IntegerField(default=0, verbose_name='总楼层数')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('campus', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='buildings',
                    to='housing.campus',
                    verbose_name='所属校区',
                )),
            ],
            options={
                'db_table': 'buildings',
                'ordering': ['sort_order', 'id'],
                'verbose_name': '楼栋',
                'verbose_name_plural': '楼栋',
                'constraints': [
                    models.UniqueConstraint(fields=['campus', 'code'], name='uniq_campus_building_code'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Floor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='楼层名称')),
                ('number', models.IntegerField(verbose_name='楼层号')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('building', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='floors',
                    to='housing.building',
                    verbose_name='所属楼栋',
                )),
            ],
            options={
                'db_table': 'floors',
                'ordering': ['sort_order', 'number'],
                'verbose_name': '楼层',
                'verbose_name_plural': '楼层',
                'constraints': [
                    models.UniqueConstraint(fields=['building', 'number'], name='uniq_building_floor_number'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='房间名称')),
                ('room_no', models.CharField(max_length=32, verbose_name='房间号')),
                ('room_type', models.CharField(
                    choices=[('standard', '标准间'), ('deluxe', '豪华间'), ('suite', '套间')],
                    default='standard',
                    max_length=20,
                    verbose_name='房间类型',
                )),
                ('capacity', models.IntegerField(default=4, verbose_name='可住人数')),
                ('area', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='面积(㎡)')),
                ('has_bathroom', models.BooleanField(default=True, verbose_name='独立卫浴')),
                ('has_aircon', models.BooleanField(default=True, verbose_name='空调')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('floor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rooms',
                    to='housing.floor',
                    verbose_name='所属楼层',
                )),
            ],
            options={
                'db_table': 'rooms',
                'ordering': ['sort_order', 'room_no'],
                'verbose_name': '房间',
                'verbose_name_plural': '房间',
                'constraints': [
                    models.UniqueConstraint(fields=['floor', 'room_no'], name='uniq_floor_room_no'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Bed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bed_no', models.CharField(max_length=16, verbose_name='床位号')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('room', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='beds',
                    to='housing.room',
                    verbose_name='所属房间',
                )),
            ],
            options={
                'db_table': 'beds',
                'ordering': ['sort_order', 'bed_no'],
                'verbose_name': '床位',
                'verbose_name_plural': '床位',
                'constraints': [
                    models.UniqueConstraint(fields=['room', 'bed_no'], name='uniq_room_bed_no'),
                ],
            },
        ),
        migrations.CreateModel(
            name='StayRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('active', '在住'), ('ended', '已退宿'), ('cancelled', '已取消')],
                    default='active',
                    max_length=20,
                    verbose_name='状态',
                )),
                ('start_date', models.DateField(verbose_name='入住日期')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='退宿日期')),
                ('remark', models.CharField(blank=True, default='', max_length=255, verbose_name='备注')),
                ('operator', models.CharField(blank=True, default='', max_length=64, verbose_name='操作人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('bed', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stay_records',
                    to='housing.bed',
                    verbose_name='床位',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stay_records',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='学生',
                )),
            ],
            options={
                'db_table': 'stay_records',
                'ordering': ['-created_at'],
                'verbose_name': '入住记录',
                'verbose_name_plural': '入住记录',
                'indexes': [
                    models.Index(fields=['user', 'status']),
                    models.Index(fields=['bed', 'status']),
                ],
            },
        ),
        migrations.CreateModel(
            name='BedChangeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(
                    choices=[('checkin', '入住'), ('checkout', '退宿'), ('transfer', '调床'), ('adjust', '管理员调整')],
                    max_length=20,
                    verbose_name='变更类型',
                )),
                ('start_date', models.DateField(blank=True, null=True, verbose_name='生效日期')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='结束日期')),
                ('reason', models.CharField(blank=True, default='', max_length=255, verbose_name='原因')),
                ('operator', models.CharField(max_length=64, verbose_name='操作人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('from_bed', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='move_out_logs',
                    to='housing.bed',
                    verbose_name='原床位',
                )),
                ('to_bed', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='move_in_logs',
                    to='housing.bed',
                    verbose_name='新床位',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bed_change_logs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='学生',
                )),
            ],
            options={
                'db_table': 'bed_change_logs',
                'ordering': ['-created_at'],
                'verbose_name': '床位变更日志',
                'verbose_name_plural': '床位变更日志',
                'indexes': [
                    models.Index(fields=['user', 'change_type']),
                ],
            },
        ),
    ]
