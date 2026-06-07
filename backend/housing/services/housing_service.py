from datetime import date
from typing import Optional

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from housing.models import (
    Bed,
    BedChangeLog,
    Building,
    Campus,
    Floor,
    Room,
    StayRecord,
)


class HousingService:

    @staticmethod
    def get_tree():
        campuses = Campus.objects.filter(is_active=True).prefetch_related(
            'buildings__floors__rooms__beds__stay_records'
        )
        result = []
        for campus in campuses:
            campus_data = {
                'id': campus.id,
                'type': 'campus',
                'name': campus.name,
                'code': campus.code,
                'children': [],
            }
            for building in campus.buildings.filter(is_active=True):
                building_data = {
                    'id': building.id,
                    'type': 'building',
                    'name': building.name,
                    'code': building.code,
                    'building_type': building.building_type,
                    'gender_limit': building.gender_limit,
                    'children': [],
                }
                for floor in building.floors.filter(is_active=True):
                    floor_data = {
                        'id': floor.id,
                        'type': 'floor',
                        'name': floor.name,
                        'number': floor.number,
                        'children': [],
                    }
                    for room in floor.rooms.filter(is_active=True):
                        beds = list(room.beds.filter(is_active=True))
                        occupied_count = sum(1 for b in beds if b.is_occupied)
                        room_data = {
                            'id': room.id,
                            'type': 'room',
                            'name': room.name,
                            'room_no': room.room_no,
                            'room_type': room.room_type,
                            'capacity': room.capacity,
                            'occupied_count': occupied_count,
                            'children': [],
                        }
                        for bed in beds:
                            student = bed.current_student
                            bed_data = {
                                'id': bed.id,
                                'type': 'bed',
                                'bed_no': bed.bed_no,
                                'is_occupied': bed.is_occupied,
                                'student_id': student.id if student else None,
                                'student_name': student.username if student else None,
                            }
                            room_data['children'].append(bed_data)
                        floor_data['children'].append(room_data)
                    building_data['children'].append(floor_data)
                campus_data['children'].append(building_data)
            result.append(campus_data)
        return result

    @staticmethod
    def check_bed_available(bed: Bed, exclude_user_id: Optional[int] = None) -> bool:
        if not bed.is_active:
            return False
        qs = StayRecord.objects.filter(bed=bed, status=StayRecord.STATUS_ACTIVE)
        if exclude_user_id:
            qs = qs.exclude(user_id=exclude_user_id)
        return not qs.exists()

    @staticmethod
    @transaction.atomic
    def assign_bed(
        user: User,
        bed: Bed,
        start_date: Optional[date] = None,
        operator: str = '',
        remark: str = '',
        reason: str = '',
    ) -> StayRecord:
        if start_date is None:
            start_date = date.today()

        if not HousingService.check_bed_available(bed):
            raise ValueError('该床位已被占用。')

        active_record = StayRecord.objects.filter(
            user=user,
            status=StayRecord.STATUS_ACTIVE,
        ).first()

        old_bed = None
        if active_record:
            old_bed = active_record.bed
            active_record.status = StayRecord.STATUS_ENDED
            active_record.end_date = start_date
            active_record.save()

            BedChangeLog.objects.create(
                user=user,
                change_type=BedChangeLog.TYPE_TRANSFER,
                from_bed=old_bed,
                to_bed=bed,
                start_date=start_date,
                reason=reason,
                operator=operator,
            )

        stay = StayRecord.objects.create(
            user=user,
            bed=bed,
            status=StayRecord.STATUS_ACTIVE,
            start_date=start_date,
            operator=operator,
            remark=remark,
        )

        if not old_bed:
            BedChangeLog.objects.create(
                user=user,
                change_type=BedChangeLog.TYPE_CHECKIN,
                from_bed=None,
                to_bed=bed,
                start_date=start_date,
                reason=reason,
                operator=operator,
            )

        return stay

    @staticmethod
    @transaction.atomic
    def check_out(
        user: User,
        end_date: Optional[date] = None,
        operator: str = '',
        reason: str = '',
    ) -> StayRecord:
        if end_date is None:
            end_date = date.today()

        active_record = StayRecord.objects.filter(
            user=user,
            status=StayRecord.STATUS_ACTIVE,
        ).first()

        if not active_record:
            raise ValueError('该学生当前没有在住记录。')

        old_bed = active_record.bed
        active_record.status = StayRecord.STATUS_ENDED
        active_record.end_date = end_date
        active_record.save()

        BedChangeLog.objects.create(
            user=user,
            change_type=BedChangeLog.TYPE_CHECKOUT,
            from_bed=old_bed,
            to_bed=None,
            end_date=end_date,
            reason=reason,
            operator=operator,
        )

        return active_record

    @staticmethod
    def get_user_current_stay(user: User):
        return StayRecord.objects.filter(
            user=user,
            status=StayRecord.STATUS_ACTIVE,
        ).select_related('bed__room__floor__building__campus').first()

    @staticmethod
    def get_user_stay_history(user: User):
        return StayRecord.objects.filter(
            user=user,
        ).select_related('bed__room__floor__building__campus').order_by('-created_at')

    @staticmethod
    def can_deactivate_room(room: Room) -> tuple:
        active_stays = StayRecord.objects.filter(
            bed__room=room,
            status=StayRecord.STATUS_ACTIVE,
        ).select_related('user')
        if active_stays.exists():
            students = [s.user.username for s in active_stays]
            return False, f'该房间仍有学生在住：{", ".join(students)}'
        return True, ''

    @staticmethod
    def can_deactivate_bed(bed: Bed) -> tuple:
        active = StayRecord.objects.filter(
            bed=bed,
            status=StayRecord.STATUS_ACTIVE,
        ).select_related('user')
        if active.exists():
            return False, f'该床位仍有学生在住：{active.first().user.username}'
        return True, ''

    @staticmethod
    @transaction.atomic
    def migrate_room_students(
        from_room: Room,
        to_room: Room,
        operator: str = '',
    ) -> int:
        active_stays = list(
            StayRecord.objects.filter(
                bed__room=from_room,
                status=StayRecord.STATUS_ACTIVE,
            ).select_related('user', 'bed')
        )
        occupied_bed_ids = list(
            StayRecord.objects.filter(status=StayRecord.STATUS_ACTIVE)
            .values_list('bed_id', flat=True)
        )
        migrated = 0
        for stay in active_stays:
            available_bed = (
                to_room.beds.filter(is_active=True)
                .exclude(id__in=occupied_bed_ids)
                .first()
            )
            if not available_bed:
                raise ValueError(f'目标房间 {to_room.room_no} 没有空余床位。')
            HousingService.assign_bed(
                user=stay.user,
                bed=available_bed,
                operator=operator,
                reason=f'从房间 {from_room.room_no} 整体迁移',
            )
            occupied_bed_ids.append(available_bed.id)
            migrated += 1
        return migrated
