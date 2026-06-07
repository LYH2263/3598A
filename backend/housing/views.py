from django.contrib.auth.models import User
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import IsAdminRole
from housing.models import (
    Bed,
    BedChangeLog,
    Building,
    Campus,
    Floor,
    Room,
    StayRecord,
)
from housing.serializers import (
    AssignBedSerializer,
    BedChangeLogSerializer,
    BedSerializer,
    BuildingSerializer,
    CampusSerializer,
    CheckOutSerializer,
    EnergyFilterSerializer,
    FloorSerializer,
    MigrateRoomSerializer,
    RoomSerializer,
    StayRecordSerializer,
)
from housing.services.energy_analytics_service import EnergyAnalyticsService
from housing.services.housing_service import HousingService


def _parse_filters(request, serializer_class=EnergyFilterSerializer):
    data = {}
    for key in request.query_params:
        val = request.query_params.getlist(key) if key.endswith('[]') or key in {
            'categories', 'campus_ids', 'building_ids', 'room_ids',
        } else request.query_params.get(key)
        if key.endswith('[]'):
            data[key[:-2]] = val
        else:
            data[key] = val
    if isinstance(data.get('categories'), str):
        data['categories'] = [x for x in data['categories'].split(',') if x.strip()]
    if isinstance(data.get('campus_ids'), str):
        data['campus_ids'] = [int(x) for x in data['campus_ids'].split(',') if x.strip()]
    if isinstance(data.get('building_ids'), str):
        data['building_ids'] = [int(x) for x in data['building_ids'].split(',') if x.strip()]
    if isinstance(data.get('room_ids'), str):
        data['room_ids'] = [int(x) for x in data['room_ids'].split(',') if x.strip()]
    for k in list(data.keys()):
        if data[k] in ('', None):
            del data[k]
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


# ============= 楼宇树结构 =============

class HousingTreeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tree = HousingService.get_tree()
        return Response(tree)


# ============= 校区 CRUD =============

class CampusListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = Campus.objects.all().order_by('sort_order', 'id')
        name = request.query_params.get('name', '').strip()
        if name:
            queryset = queryset.filter(name__icontains=name)
        return Response(CampusSerializer(queryset[:500], many=True).data)

    def post(self, request):
        serializer = CampusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campus = serializer.save()
        return Response(CampusSerializer(campus).data, status=status.HTTP_201_CREATED)


class CampusDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return Campus.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '校区不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CampusSerializer(obj).data)

    def put(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '校区不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CampusSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CampusSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '校区不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if obj.buildings.exists():
            return Response({'detail': '该校区下存在楼栋，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============= 楼栋 CRUD =============

class BuildingListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = Building.objects.select_related('campus').all().order_by('sort_order', 'id')
        campus_id = request.query_params.get('campus_id', '').strip()
        name = request.query_params.get('name', '').strip()
        if campus_id:
            queryset = queryset.filter(campus_id=campus_id)
        if name:
            queryset = queryset.filter(name__icontains=name)
        return Response(BuildingSerializer(queryset[:500], many=True).data)

    def post(self, request):
        serializer = BuildingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(BuildingSerializer(obj).data, status=status.HTTP_201_CREATED)


class BuildingDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return Building.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '楼栋不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BuildingSerializer(obj).data)

    def put(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '楼栋不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BuildingSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BuildingSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '楼栋不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if obj.floors.exists():
            return Response({'detail': '该楼栋下存在楼层，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============= 楼层 CRUD =============

class FloorListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = Floor.objects.select_related('building', 'building__campus').all().order_by('sort_order', 'number')
        building_id = request.query_params.get('building_id', '').strip()
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        return Response(FloorSerializer(queryset[:500], many=True).data)

    def post(self, request):
        serializer = FloorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(FloorSerializer(obj).data, status=status.HTTP_201_CREATED)


class FloorDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return Floor.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '楼层不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FloorSerializer(obj).data)

    def put(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '楼层不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = FloorSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FloorSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '楼层不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if obj.rooms.exists():
            return Response({'detail': '该楼层下存在房间，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============= 房间 CRUD =============

class RoomListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = Room.objects.select_related(
            'floor', 'floor__building', 'floor__building__campus'
        ).all().order_by('sort_order', 'room_no')
        floor_id = request.query_params.get('floor_id', '').strip()
        building_id = request.query_params.get('building_id', '').strip()
        keyword = request.query_params.get('keyword', '').strip()
        if floor_id:
            queryset = queryset.filter(floor_id=floor_id)
        if building_id:
            queryset = queryset.filter(floor__building_id=building_id)
        if keyword:
            queryset = queryset.filter(room_no__icontains=keyword)
        return Response(RoomSerializer(queryset[:500], many=True).data)

    def post(self, request):
        serializer = RoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(RoomSerializer(obj).data, status=status.HTTP_201_CREATED)


class RoomDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return Room.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '房间不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RoomSerializer(obj).data)

    def put(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '房间不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if 'is_active' in request.data and not request.data['is_active']:
            can, reason = HousingService.can_deactivate_room(obj)
            if not can:
                return Response({'detail': reason}, status=status.HTTP_400_BAD_REQUEST)
        serializer = RoomSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RoomSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '房间不存在。'}, status=status.HTTP_404_NOT_FOUND)
        can, reason = HousingService.can_deactivate_room(obj)
        if not can:
            return Response({'detail': reason}, status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoomMigrateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = MigrateRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from_room = Room.objects.get(id=serializer.validated_data['from_room_id'])
        to_room = Room.objects.get(id=serializer.validated_data['to_room_id'])
        try:
            count = HousingService.migrate_room_students(
                from_room=from_room,
                to_room=to_room,
                operator=request.user.username,
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'migrated_count': count})


# ============= 床位 CRUD =============

class BedListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = Bed.objects.select_related(
            'room', 'room__floor', 'room__floor__building', 'room__floor__building__campus'
        ).all().order_by('sort_order', 'bed_no')
        room_id = request.query_params.get('room_id', '').strip()
        building_id = request.query_params.get('building_id', '').strip()
        available = request.query_params.get('available_only', '').strip()
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        if building_id:
            queryset = queryset.filter(room__floor__building_id=building_id)
        data = BedSerializer(queryset[:500], many=True).data
        if available:
            data = [b for b in data if not b['is_occupied']]
        return Response(data)

    def post(self, request):
        serializer = BedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(BedSerializer(obj).data, status=status.HTTP_201_CREATED)


class BedDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return Bed.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '床位不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BedSerializer(obj).data)

    def put(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '床位不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if 'is_active' in request.data and not request.data['is_active']:
            can, reason = HousingService.can_deactivate_bed(obj)
            if not can:
                return Response({'detail': reason}, status=status.HTTP_400_BAD_REQUEST)
        serializer = BedSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BedSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'detail': '床位不存在。'}, status=status.HTTP_404_NOT_FOUND)
        can, reason = HousingService.can_deactivate_bed(obj)
        if not can:
            return Response({'detail': reason}, status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============= 入住管理 =============

class AssignBedAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = AssignBedSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            stay = serializer.save()
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StayRecordSerializer(stay).data, status=status.HTTP_201_CREATED)


class CheckOutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = CheckOutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            stay = serializer.save()
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StayRecordSerializer(stay).data)


class MyStayCurrentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        stay = HousingService.get_user_current_stay(request.user)
        if not stay:
            return Response({'detail': '暂无在住记录。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StayRecordSerializer(stay).data)


class MyStayHistoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        records = HousingService.get_user_stay_history(request.user)
        return Response(StayRecordSerializer(records, many=True).data)


class StayRecordListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = StayRecord.objects.select_related(
            'user', 'bed__room__floor__building__campus'
        ).all().order_by('-created_at')
        user_id = request.query_params.get('user_id', '').strip()
        bed_id = request.query_params.get('bed_id', '').strip()
        room_id = request.query_params.get('room_id', '').strip()
        status = request.query_params.get('status', '').strip()
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if bed_id:
            queryset = queryset.filter(bed_id=bed_id)
        if room_id:
            queryset = queryset.filter(bed__room_id=room_id)
        if status:
            queryset = queryset.filter(status=status)
        return Response(StayRecordSerializer(queryset[:500], many=True).data)


class BedChangeLogListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = BedChangeLog.objects.select_related(
            'user', 'from_bed__room', 'to_bed__room'
        ).all().order_by('-created_at')
        user_id = request.query_params.get('user_id', '').strip()
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return Response(BedChangeLogSerializer(queryset[:500], many=True).data)


# ============= 能耗分析 =============

class EnergyRoomRankingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters(request)
        top_n = filters.get('top_n', 20)
        data = EnergyAnalyticsService.by_room_ranking(filters, request.user, top_n)
        return Response(data)


class EnergyBuildingRankingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters(request)
        top_n = filters.get('top_n', 20)
        data = EnergyAnalyticsService.by_building_ranking(filters, request.user, top_n)
        return Response(data)


class EnergyMonthlyTrendAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters(request)
        group_by = filters.get('group_by', 'building')
        data = EnergyAnalyticsService.by_monthly_trend(filters, request.user, group_by)
        return Response(data)


class DashboardTopBuildingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        top_n = int(request.query_params.get('top_n', 10))
        data = EnergyAnalyticsService.dashboard_top_buildings(top_n)
        return Response(data)
