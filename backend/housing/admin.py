from django.contrib import admin

from housing.models import (
    Bed,
    BedChangeLog,
    Building,
    Campus,
    Floor,
    Room,
    StayRecord,
)


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'campus', 'building_type', 'is_active', 'created_at')
    list_filter = ('building_type', 'is_active', 'campus')
    search_fields = ('name', 'code')


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'number', 'building', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'room_no', 'floor', 'room_type', 'capacity', 'is_active', 'created_at')
    list_filter = ('room_type', 'is_active')
    search_fields = ('name', 'room_no')


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ('id', 'bed_no', 'room', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('bed_no',)


@admin.register(StayRecord)
class StayRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'bed', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username',)
    raw_id_fields = ('user', 'bed')


@admin.register(BedChangeLog)
class BedChangeLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'change_type', 'from_bed', 'to_bed', 'operator', 'created_at')
    list_filter = ('change_type',)
    search_fields = ('user__username', 'operator')
    raw_id_fields = ('user', 'from_bed', 'to_bed')
