from django.contrib.auth.models import User
from django.db import models
from django.db.models import UniqueConstraint


class Campus(models.Model):
    name = models.CharField(max_length=128, verbose_name='校区名称')
    code = models.CharField(max_length=32, unique=True, verbose_name='校区编码')
    address = models.CharField(max_length=255, blank=True, default='', verbose_name='地址')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'campus'
        ordering = ['sort_order', 'id']
        verbose_name = '校区'
        verbose_name_plural = '校区'

    def __str__(self) -> str:
        return self.name


class Building(models.Model):
    TYPE_DORM = 'dorm'
    TYPE_TEACHING = 'teaching'
    TYPE_OFFICE = 'office'
    TYPE_MIXED = 'mixed'

    TYPE_CHOICES = [
        (TYPE_DORM, '宿舍楼'),
        (TYPE_TEACHING, '教学楼'),
        (TYPE_OFFICE, '办公楼'),
        (TYPE_MIXED, '综合楼'),
    ]

    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_MIXED = 'mixed'

    GENDER_CHOICES = [
        (GENDER_MALE, '男生楼'),
        (GENDER_FEMALE, '女生楼'),
        (GENDER_MIXED, '男女混合'),
    ]

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='buildings', verbose_name='所属校区')
    name = models.CharField(max_length=128, verbose_name='楼栋名称')
    code = models.CharField(max_length=32, verbose_name='楼栋编码')
    building_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_DORM, verbose_name='楼栋类型')
    gender_limit = models.CharField(max_length=20, choices=GENDER_CHOICES, default=GENDER_MIXED, verbose_name='性别限制')
    total_floors = models.IntegerField(default=0, verbose_name='总楼层数')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'buildings'
        ordering = ['sort_order', 'id']
        verbose_name = '楼栋'
        verbose_name_plural = '楼栋'
        constraints = [
            UniqueConstraint(fields=['campus', 'code'], name='uniq_campus_building_code'),
        ]

    def __str__(self) -> str:
        return f'{self.campus.name} - {self.name}'


class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors', verbose_name='所属楼栋')
    name = models.CharField(max_length=64, verbose_name='楼层名称')
    number = models.IntegerField(verbose_name='楼层号')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'floors'
        ordering = ['sort_order', 'number']
        verbose_name = '楼层'
        verbose_name_plural = '楼层'
        constraints = [
            UniqueConstraint(fields=['building', 'number'], name='uniq_building_floor_number'),
        ]

    def __str__(self) -> str:
        return f'{self.building.name} - {self.name}'


class Room(models.Model):
    TYPE_STANDARD = 'standard'
    TYPE_DELUXE = 'deluxe'
    TYPE_SUITE = 'suite'

    TYPE_CHOICES = [
        (TYPE_STANDARD, '标准间'),
        (TYPE_DELUXE, '豪华间'),
        (TYPE_SUITE, '套间'),
    ]

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='rooms', verbose_name='所属楼层')
    name = models.CharField(max_length=64, verbose_name='房间名称')
    room_no = models.CharField(max_length=32, verbose_name='房间号')
    room_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_STANDARD, verbose_name='房间类型')
    capacity = models.IntegerField(default=4, verbose_name='可住人数')
    area = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='面积(㎡)')
    has_bathroom = models.BooleanField(default=True, verbose_name='独立卫浴')
    has_aircon = models.BooleanField(default=True, verbose_name='空调')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'rooms'
        ordering = ['sort_order', 'room_no']
        verbose_name = '房间'
        verbose_name_plural = '房间'
        constraints = [
            UniqueConstraint(fields=['floor', 'room_no'], name='uniq_floor_room_no'),
        ]

    def __str__(self) -> str:
        return f'{self.floor.building.name} - {self.room_no}'

    @property
    def building(self):
        return self.floor.building

    @property
    def campus(self):
        return self.floor.building.campus


class Bed(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='beds', verbose_name='所属房间')
    bed_no = models.CharField(max_length=16, verbose_name='床位号')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'beds'
        ordering = ['sort_order', 'bed_no']
        verbose_name = '床位'
        verbose_name_plural = '床位'
        constraints = [
            UniqueConstraint(fields=['room', 'bed_no'], name='uniq_room_bed_no'),
        ]

    def __str__(self) -> str:
        return f'{self.room} - {self.bed_no}'

    @property
    def floor(self):
        return self.room.floor

    @property
    def building(self):
        return self.room.floor.building

    @property
    def campus(self):
        return self.room.floor.building.campus

    @property
    def is_occupied(self):
        return StayRecord.objects.filter(
            bed=self,
            status=StayRecord.STATUS_ACTIVE,
        ).exists()

    @property
    def current_student(self):
        active = StayRecord.objects.filter(
            bed=self,
            status=StayRecord.STATUS_ACTIVE,
        ).select_related('user').first()
        return active.user if active else None


class StayRecord(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_ENDED = 'ended'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, '在住'),
        (STATUS_ENDED, '已退宿'),
        (STATUS_CANCELLED, '已取消'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stay_records', verbose_name='学生')
    bed = models.ForeignKey(Bed, on_delete=models.CASCADE, related_name='stay_records', verbose_name='床位')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, verbose_name='状态')
    start_date = models.DateField(verbose_name='入住日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='退宿日期')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    operator = models.CharField(max_length=64, blank=True, default='', verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'stay_records'
        ordering = ['-created_at']
        verbose_name = '入住记录'
        verbose_name_plural = '入住记录'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['bed', 'status']),
        ]

    def __str__(self) -> str:
        return f'{self.user.username} - {self.bed}'


class BedChangeLog(models.Model):
    TYPE_CHECKIN = 'checkin'
    TYPE_CHECKOUT = 'checkout'
    TYPE_TRANSFER = 'transfer'
    TYPE_ADJUST = 'adjust'

    TYPE_CHOICES = [
        (TYPE_CHECKIN, '入住'),
        (TYPE_CHECKOUT, '退宿'),
        (TYPE_TRANSFER, '调床'),
        (TYPE_ADJUST, '管理员调整'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bed_change_logs', verbose_name='学生')
    change_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='变更类型')
    from_bed = models.ForeignKey(
        Bed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='move_out_logs',
        verbose_name='原床位',
    )
    to_bed = models.ForeignKey(
        Bed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='move_in_logs',
        verbose_name='新床位',
    )
    start_date = models.DateField(null=True, blank=True, verbose_name='生效日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    reason = models.CharField(max_length=255, blank=True, default='', verbose_name='原因')
    operator = models.CharField(max_length=64, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'bed_change_logs'
        ordering = ['-created_at']
        verbose_name = '床位变更日志'
        verbose_name_plural = '床位变更日志'
        indexes = [
            models.Index(fields=['user', 'change_type']),
        ]

    def __str__(self) -> str:
        return f'{self.user.username} - {self.get_change_type_display()}'
