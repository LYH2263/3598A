from datetime import date

from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import Profile
from housing.models import (
    Bed,
    BedChangeLog,
    Building,
    Campus,
    Floor,
    Room,
    StayRecord,
)
from housing.services.housing_service import HousingService


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ('id', 'name', 'code', 'address', 'description', 'is_active', 'sort_order', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class BuildingSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source='campus.name', read_only=True)
    building_type_display = serializers.CharField(source='get_building_type_display', read_only=True)
    gender_limit_display = serializers.CharField(source='get_gender_limit_display', read_only=True)

    class Meta:
        model = Building
        fields = (
            'id', 'campus', 'campus_name', 'name', 'code', 'building_type', 'building_type_display',
            'gender_limit', 'gender_limit_display', 'total_floors', 'description',
            'is_active', 'sort_order', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'campus_name', 'building_type_display', 'gender_limit_display', 'created_at', 'updated_at')


class FloorSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    campus_name = serializers.CharField(source='building.campus.name', read_only=True)

    class Meta:
        model = Floor
        fields = (
            'id', 'building', 'building_name', 'campus_name', 'name', 'number', 'description',
            'is_active', 'sort_order', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'building_name', 'campus_name', 'created_at', 'updated_at')


class RoomSerializer(serializers.ModelSerializer):
    floor_name = serializers.CharField(source='floor.name', read_only=True)
    floor_number = serializers.IntegerField(source='floor.number', read_only=True)
    building_name = serializers.CharField(source='floor.building.name', read_only=True)
    campus_name = serializers.CharField(source='floor.building.campus.name', read_only=True)
    room_type_display = serializers.CharField(source='get_room_type_display', read_only=True)
    occupied_count = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            'id', 'floor', 'floor_name', 'floor_number', 'building_name', 'campus_name',
            'name', 'room_no', 'room_type', 'room_type_display', 'capacity', 'occupied_count',
            'area', 'has_bathroom', 'has_aircon', 'description',
            'is_active', 'sort_order', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'floor_name', 'floor_number', 'building_name', 'campus_name', 'room_type_display', 'occupied_count', 'created_at', 'updated_at')

    def get_occupied_count(self, obj):
        return StayRecord.objects.filter(
            bed__room=obj,
            status=StayRecord.STATUS_ACTIVE,
        ).count()


class BedSerializer(serializers.ModelSerializer):
    room_no = serializers.CharField(source='room.room_no', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    floor_number = serializers.IntegerField(source='room.floor.number', read_only=True)
    building_name = serializers.CharField(source='room.floor.building.name', read_only=True)
    campus_name = serializers.CharField(source='room.floor.building.campus.name', read_only=True)
    is_occupied = serializers.SerializerMethodField()
    current_student_id = serializers.SerializerMethodField()
    current_student_name = serializers.SerializerMethodField()

    class Meta:
        model = Bed
        fields = (
            'id', 'room', 'room_no', 'room_name', 'floor_number', 'building_name', 'campus_name',
            'bed_no', 'description', 'is_occupied', 'current_student_id', 'current_student_name',
            'is_active', 'sort_order', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'room_no', 'room_name', 'floor_number', 'building_name', 'campus_name',
            'is_occupied', 'current_student_id', 'current_student_name', 'created_at', 'updated_at',
        )

    def get_is_occupied(self, obj):
        return obj.is_occupied

    def get_current_student_id(self, obj):
        student = obj.current_student
        return student.id if student else None

    def get_current_student_name(self, obj):
        student = obj.current_student
        return student.username if student else None


class StayRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    student_id = serializers.CharField(source='user.profile.student_id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    bed_no = serializers.CharField(source='bed.bed_no', read_only=True)
    room_no = serializers.CharField(source='bed.room.room_no', read_only=True)
    floor_number = serializers.IntegerField(source='bed.room.floor.number', read_only=True)
    building_name = serializers.CharField(source='bed.room.floor.building.name', read_only=True)
    campus_name = serializers.CharField(source='bed.room.floor.building.campus.name', read_only=True)

    class Meta:
        model = StayRecord
        fields = (
            'id', 'user', 'user_name', 'student_id', 'bed', 'bed_no',
            'room_no', 'floor_number', 'building_name', 'campus_name',
            'status', 'status_display', 'start_date', 'end_date',
            'remark', 'operator', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'user_name', 'student_id', 'bed_no', 'room_no', 'floor_number', 'building_name', 'campus_name', 'status_display', 'created_at', 'updated_at')


class BedChangeLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    from_bed_no = serializers.CharField(source='from_bed.bed_no', read_only=True, allow_null=True)
    from_room_no = serializers.CharField(source='from_bed.room.room_no', read_only=True, allow_null=True)
    to_bed_no = serializers.CharField(source='to_bed.bed_no', read_only=True, allow_null=True)
    to_room_no = serializers.CharField(source='to_bed.room.room_no', read_only=True, allow_null=True)

    class Meta:
        model = BedChangeLog
        fields = (
            'id', 'user', 'user_name', 'change_type', 'change_type_display',
            'from_bed', 'from_bed_no', 'from_room_no',
            'to_bed', 'to_bed_no', 'to_room_no',
            'start_date', 'end_date', 'reason', 'operator', 'created_at',
        )
        read_only_fields = ('id', 'user_name', 'change_type_display', 'from_bed_no', 'from_room_no', 'to_bed_no', 'to_room_no', 'created_at')


class AssignBedSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    bed_id = serializers.IntegerField()
    start_date = serializers.DateField(required=False, default=date.today)
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate_user_id(self, value):
        user = User.objects.filter(id=value).first()
        if not user:
            raise serializers.ValidationError('用户不存在。')
        return value

    def validate_bed_id(self, value):
        bed = Bed.objects.filter(id=value, is_active=True).first()
        if not bed:
            raise serializers.ValidationError('床位不存在或已停用。')
        return value

    def create(self, validated_data):
        request = self.context['request']
        user = User.objects.get(id=validated_data['user_id'])
        bed = Bed.objects.get(id=validated_data['bed_id'])
        return HousingService.assign_bed(
            user=user,
            bed=bed,
            start_date=validated_data.get('start_date'),
            operator=request.user.username,
            remark=validated_data.get('remark', ''),
            reason=validated_data.get('reason', ''),
        )


class CheckOutSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    end_date = serializers.DateField(required=False, default=date.today)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate_user_id(self, value):
        user = User.objects.filter(id=value).first()
        if not user:
            raise serializers.ValidationError('用户不存在。')
        return value

    def create(self, validated_data):
        request = self.context['request']
        user = User.objects.get(id=validated_data['user_id'])
        return HousingService.check_out(
            user=user,
            end_date=validated_data.get('end_date'),
            operator=request.user.username,
            reason=validated_data.get('reason', ''),
        )


class MigrateRoomSerializer(serializers.Serializer):
    from_room_id = serializers.IntegerField()
    to_room_id = serializers.IntegerField()

    def validate_from_room_id(self, value):
        room = Room.objects.filter(id=value, is_active=True).first()
        if not room:
            raise serializers.ValidationError('源房间不存在或已停用。')
        return value

    def validate_to_room_id(self, value):
        room = Room.objects.filter(id=value, is_active=True).first()
        if not room:
            raise serializers.ValidationError('目标房间不存在或已停用。')
        return value


class EnergyFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=['water', 'electricity']),
        required=False,
        default=list,
    )
    campus_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    building_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    room_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    top_n = serializers.IntegerField(min_value=1, max_value=200, required=False, default=20)
    group_by = serializers.ChoiceField(choices=['building', 'room'], required=False, default='building')
