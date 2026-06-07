from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Cast, TruncMonth

from accounts.models import Profile
from billing.models import ConsumptionRecord
from housing.models import Building, Room, StayRecord


class EnergyAnalyticsService:

    @staticmethod
    def _base_queryset(filters: dict, user: Optional[User] = None):
        qs = ConsumptionRecord.objects.all()

        role = getattr(getattr(user, 'profile', None), 'role', None)
        if role != Profile.ROLE_ADMIN:
            qs = qs.filter(user=user)

        if filters.get('start_date'):
            qs = qs.filter(created_at__date__gte=filters['start_date'])
        if filters.get('end_date'):
            qs = qs.filter(created_at__date__lte=filters['end_date'])
        if filters.get('categories'):
            qs = qs.filter(category__in=filters['categories'])
        if filters.get('building_ids'):
            qs = qs.filter(room__floor__building_id__in=filters['building_ids'])
        if filters.get('room_ids'):
            qs = qs.filter(room_id__in=filters['room_ids'])
        if filters.get('campus_ids'):
            qs = qs.filter(room__floor__building__campus_id__in=filters['campus_ids'])

        return qs

    @staticmethod
    def _infer_room_for_user(user: User, at_date=None):
        if at_date is None:
            at_date = datetime.now().date()
        stay = StayRecord.objects.filter(
            user=user,
            start_date__lte=at_date,
        ).filter(
            Q(end_date__gte=at_date) | Q(end_date__isnull=True)
        ).select_related('bed__room').order_by('-start_date').first()
        if stay:
            return stay.bed.room
        return None

    @staticmethod
    def by_room_ranking(filters: dict, user: Optional[User] = None, top_n: int = 20):
        qs = EnergyAnalyticsService._base_queryset(filters, user)
        ranking = (
            qs.filter(room__isnull=False)
            .annotate(
                room_id=F('room_id'),
                room_no=F('room__room_no'),
                building_id=F('room__floor__building_id'),
                building_name=F('room__floor__building__name'),
            )
            .values('room_id', 'room_no', 'building_id', 'building_name')
            .annotate(
                total_cost=Sum('cost_amount'),
                total_usage=Sum('usage'),
                water_cost=Sum('cost_amount', filter=Q(category='water')),
                electricity_cost=Sum('cost_amount', filter=Q(category='electricity')),
                water_usage=Sum('usage', filter=Q(category='water')),
                electricity_usage=Sum('usage', filter=Q(category='electricity')),
                count=Count('id'),
            )
            .order_by('-total_cost')[:top_n]
        )
        data = []
        for idx, row in enumerate(ranking, 1):
            data.append({
                'rank': idx,
                'room_id': row['room_id'],
                'room_no': row['room_no'],
                'building_id': row['building_id'],
                'building_name': row['building_name'],
                'total_cost': float(row['total_cost'] or 0),
                'total_usage': float(row['total_usage'] or 0),
                'water_cost': float(row['water_cost'] or 0),
                'electricity_cost': float(row['electricity_cost'] or 0),
                'water_usage': float(row['water_usage'] or 0),
                'electricity_usage': float(row['electricity_usage'] or 0),
                'count': row['count'],
            })
        return data

    @staticmethod
    def by_building_ranking(filters: dict, user: Optional[User] = None, top_n: int = 20):
        qs = EnergyAnalyticsService._base_queryset(filters, user)
        ranking = (
            qs.filter(room__isnull=False)
            .annotate(
                building_id=F('room__floor__building_id'),
                building_name=F('room__floor__building__name'),
                campus_id=F('room__floor__building__campus_id'),
                campus_name=F('room__floor__building__campus__name'),
            )
            .values('building_id', 'building_name', 'campus_id', 'campus_name')
            .annotate(
                total_cost=Sum('cost_amount'),
                total_usage=Sum('usage'),
                water_cost=Sum('cost_amount', filter=Q(category='water')),
                electricity_cost=Sum('cost_amount', filter=Q(category='electricity')),
                water_usage=Sum('usage', filter=Q(category='water')),
                electricity_usage=Sum('usage', filter=Q(category='electricity')),
                room_count=Count('room_id', distinct=True),
                count=Count('id'),
            )
            .order_by('-total_cost')[:top_n]
        )
        data = []
        for idx, row in enumerate(ranking, 1):
            data.append({
                'rank': idx,
                'building_id': row['building_id'],
                'building_name': row['building_name'],
                'campus_id': row['campus_id'],
                'campus_name': row['campus_name'],
                'total_cost': float(row['total_cost'] or 0),
                'total_usage': float(row['total_usage'] or 0),
                'water_cost': float(row['water_cost'] or 0),
                'electricity_cost': float(row['electricity_cost'] or 0),
                'water_usage': float(row['water_usage'] or 0),
                'electricity_usage': float(row['electricity_usage'] or 0),
                'room_count': row['room_count'],
                'count': row['count'],
            })
        return data

    @staticmethod
    def by_monthly_trend(filters: dict, user: Optional[User] = None, group_by: str = 'building'):
        qs = EnergyAnalyticsService._base_queryset(filters, user)
        qs = qs.filter(room__isnull=False)

        if group_by == 'room':
            qs = qs.annotate(group_id=F('room_id'), group_name=F('room__room_no'))
        else:
            qs = qs.annotate(group_id=F('room__floor__building_id'), group_name=F('room__floor__building__name'))

        trend = (
            qs.annotate(month=TruncMonth('created_at'))
            .values('group_id', 'group_name', 'month')
            .annotate(
                total_cost=Sum('cost_amount'),
                total_usage=Sum('usage'),
                water_cost=Sum('cost_amount', filter=Q(category='water')),
                electricity_cost=Sum('cost_amount', filter=Q(category='electricity')),
                count=Count('id'),
            )
            .order_by('group_id', 'month')
        )
        result = {}
        for row in trend:
            gid = row['group_id']
            if gid not in result:
                result[gid] = {
                    'group_id': gid,
                    'group_name': row['group_name'],
                    'data': [],
                }
            result[gid]['data'].append({
                'month': row['month'].strftime('%Y-%m') if row['month'] else '',
                'total_cost': float(row['total_cost'] or 0),
                'total_usage': float(row['total_usage'] or 0),
                'water_cost': float(row['water_cost'] or 0),
                'electricity_cost': float(row['electricity_cost'] or 0),
                'count': row['count'],
            })
        return list(result.values())

    @staticmethod
    def dashboard_top_buildings(top_n: int = 10):
        last_30 = datetime.now().date() - timedelta(days=30)
        qs = ConsumptionRecord.objects.filter(
            room__isnull=False,
            created_at__date__gte=last_30,
        )
        ranking = (
            qs.annotate(
                building_id=F('room__floor__building_id'),
                building_name=F('room__floor__building__name'),
            )
            .values('building_id', 'building_name')
            .annotate(
                total_cost=Sum('cost_amount'),
                total_usage=Sum('usage'),
                water_cost=Sum('cost_amount', filter=Q(category='water')),
                electricity_cost=Sum('cost_amount', filter=Q(category='electricity')),
            )
            .order_by('-total_cost')[:top_n]
        )
        data = []
        for idx, row in enumerate(ranking, 1):
            data.append({
                'rank': idx,
                'building_id': row['building_id'],
                'building_name': row['building_name'],
                'total_cost': float(row['total_cost'] or 0),
                'total_usage': float(row['total_usage'] or 0),
                'water_cost': float(row['water_cost'] or 0),
                'electricity_cost': float(row['electricity_cost'] or 0),
            })
        if not data:
            data = []
        return data
