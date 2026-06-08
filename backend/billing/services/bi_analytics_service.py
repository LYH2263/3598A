from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.contrib.auth.models import User
from django.db import connection
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    DecimalField,
    F,
    IntegerField,
    Max,
    Min,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import (
    Cast,
    Coalesce,
    ExtractHour,
    ExtractMonth,
    ExtractWeek,
    ExtractWeekDay,
    ExtractYear,
    TruncDate,
    TruncMonth,
    TruncWeek,
)

from accounts.models import Profile
from billing.models import ConsumptionRecord


class BIAnalyticsService:
    TIME_PERIOD_MORNING = 'morning'
    TIME_PERIOD_NOON = 'noon'
    TIME_PERIOD_EVENING = 'evening'
    TIME_PERIOD_NIGHT = 'night'

    TIME_PERIOD_CHOICES = [
        (TIME_PERIOD_MORNING, '早晨(6-12)'),
        (TIME_PERIOD_NOON, '午间(12-18)'),
        (TIME_PERIOD_EVENING, '傍晚(18-24)'),
        (TIME_PERIOD_NIGHT, '夜间(0-6)'),
    ]

    @staticmethod
    def _build_base_queryset(filters: dict, user: Optional[User] = None):
        role = getattr(getattr(user, 'profile', None), 'role', Profile.ROLE_STUDENT)
        qs = ConsumptionRecord.objects.select_related('user', 'user__profile')

        if role != Profile.ROLE_ADMIN:
            qs = qs.filter(user=user)

        if filters.get('start_date'):
            qs = qs.filter(created_at__date__gte=filters['start_date'])
        if filters.get('end_date'):
            qs = qs.filter(created_at__date__lte=filters['end_date'])
        if filters.get('user_ids'):
            qs = qs.filter(user_id__in=filters['user_ids'])
        if filters.get('categories'):
            qs = qs.filter(category__in=filters['categories'])
        if filters.get('channels'):
            qs = qs.filter(channel__in=filters['channels'])
        if filters.get('min_amount') is not None:
            qs = qs.filter(cost_amount__gte=filters['min_amount'])
        if filters.get('max_amount') is not None:
            qs = qs.filter(cost_amount__lte=filters['max_amount'])
        if filters.get('buildings'):
            qs = qs.filter(building__in=filters['buildings'])
        if filters.get('rooms'):
            qs = qs.filter(room__in=filters['rooms'])

        return qs

    @staticmethod
    def _get_category_label(value: str) -> str:
        label_map = dict(ConsumptionRecord.CATEGORY_CHOICES)
        return label_map.get(value, value)

    @staticmethod
    def _get_channel_label(value: str) -> str:
        label_map = dict(ConsumptionRecord.CHANNEL_CHOICES)
        return label_map.get(value, value)

    @staticmethod
    def _decimal_to_float(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    @staticmethod
    def _calc_growth_rate(current, previous) -> Optional[float]:
        cur = BIAnalyticsService._decimal_to_float(current)
        prev = BIAnalyticsService._decimal_to_float(previous)
        if prev == 0:
            return None
        return round((cur - prev) / prev * 100, 2)

    @staticmethod
    def by_category(filters: dict, user: Optional[User] = None) -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)
        stats = list(
            qs.values('category')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
                avg_cost=Coalesce(Avg('cost_amount'), Value(0)),
            )
            .order_by('-total_cost')
        )
        grand_total = BIAnalyticsService._decimal_to_float(
            qs.aggregate(total=Sum('cost_amount'))['total'] or 0
        )
        data = []
        for item in stats:
            total = BIAnalyticsService._decimal_to_float(item['total_cost'])
            data.append({
                'category': item['category'],
                'category_label': BIAnalyticsService._get_category_label(item['category']),
                'total_cost': total,
                'total_usage': BIAnalyticsService._decimal_to_float(item['total_usage']),
                'count': item['count'],
                'avg_cost': BIAnalyticsService._decimal_to_float(item['avg_cost']),
                'percentage': round(total / grand_total * 100, 2) if grand_total > 0 else 0,
            })
        return {
            'data': data,
            'items': data,
            'summary': {
                'grand_total': grand_total,
                'category_count': len(data),
                'record_count': BIAnalyticsService._decimal_to_float(
                    qs.aggregate(c=Count('id'))['c'] or 0
                ),
            },
        }

    @staticmethod
    def by_time_trend(filters: dict, user: Optional[User] = None, granularity: str = 'day') -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)

        if granularity == 'month':
            trunc_fn = TruncMonth
        elif granularity == 'week':
            trunc_fn = TruncWeek
        else:
            trunc_fn = TruncDate

        trend = list(
            qs.annotate(period=trunc_fn('created_at'))
            .values('period')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
                water_cost=Coalesce(
                    Sum(Case(When(category='water', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
                electricity_cost=Coalesce(
                    Sum(Case(When(category='electricity', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
            )
            .order_by('period')
        )

        data = []
        for item in trend:
            period_val = item['period']
            if hasattr(period_val, 'strftime'):
                if granularity == 'month':
                    period_label = period_val.strftime('%Y-%m')
                elif granularity == 'week':
                    period_label = period_val.strftime('%Y-W%W')
                else:
                    period_label = period_val.strftime('%Y-%m-%d')
            else:
                period_label = str(period_val) if period_val else ''
            data.append({
                'period': period_label,
                'total_cost': BIAnalyticsService._decimal_to_float(item['total_cost']),
                'total_usage': BIAnalyticsService._decimal_to_float(item['total_usage']),
                'count': item['count'],
                'water_cost': BIAnalyticsService._decimal_to_float(item['water_cost']),
                'electricity_cost': BIAnalyticsService._decimal_to_float(item['electricity_cost']),
            })

        totals = qs.aggregate(
            total_cost=Coalesce(Sum('cost_amount'), Value(0)),
            total_usage=Coalesce(Sum('usage'), Value(0)),
            record_count=Count('id'),
        )
        return {
            'granularity': granularity,
            'data': data,
            'items': data,
            'summary': {
                'total_cost': BIAnalyticsService._decimal_to_float(totals['total_cost']),
                'total_usage': BIAnalyticsService._decimal_to_float(totals['total_usage']),
                'record_count': totals['record_count'] or 0,
                'period_count': len(data),
            },
        }

    @staticmethod
    def by_channel(filters: dict, user: Optional[User] = None) -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)
        stats = list(
            qs.values('channel')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
            )
            .order_by('-total_cost')
        )
        grand_total = BIAnalyticsService._decimal_to_float(
            qs.aggregate(total=Sum('cost_amount'))['total'] or 0
        )
        data = []
        for item in stats:
            total = BIAnalyticsService._decimal_to_float(item['total_cost'])
            data.append({
                'channel': item['channel'],
                'channel_label': BIAnalyticsService._get_channel_label(item['channel']),
                'total_cost': total,
                'total_usage': BIAnalyticsService._decimal_to_float(item['total_usage']),
                'count': item['count'],
                'percentage': round(total / grand_total * 100, 2) if grand_total > 0 else 0,
            })
        return {
            'data': data,
            'items': data,
            'summary': {
                'grand_total': grand_total,
                'channel_count': len(data),
            },
        }

    @staticmethod
    def top_students(filters: dict, user: Optional[User] = None, top_n: int = 10) -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)
        stats = list(
            qs.values('user_id', 'user__username', 'user__profile__student_id')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
                water_cost=Coalesce(
                    Sum(Case(When(category='water', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
                electricity_cost=Coalesce(
                    Sum(Case(When(category='electricity', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
            )
            .order_by('-total_cost')[:top_n]
        )
        data = []
        rank = 1
        for item in stats:
            data.append({
                'rank': rank,
                'user_id': item['user_id'],
                'username': item['user__username'],
                'student_id': item['user__profile__student_id'] or '',
                'total_cost': BIAnalyticsService._decimal_to_float(item['total_cost']),
                'total_usage': BIAnalyticsService._decimal_to_float(item['total_usage']),
                'count': item['count'],
                'water_cost': BIAnalyticsService._decimal_to_float(item['water_cost']),
                'electricity_cost': BIAnalyticsService._decimal_to_float(item['electricity_cost']),
            })
            rank += 1
        return {
            'top_n': top_n,
            'data': data,
            'items': data,
        }

    @staticmethod
    def by_building_room(filters: dict, user: Optional[User] = None) -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)
        by_building = list(
            qs.exclude(building='')
            .values('building')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
                room_count=Count('room', distinct=True),
            )
            .order_by('-total_cost')
        )
        buildings = []
        for item in by_building:
            buildings.append({
                'building': item['building'],
                'total_cost': BIAnalyticsService._decimal_to_float(item['total_cost']),
                'total_usage': BIAnalyticsService._decimal_to_float(item['total_usage']),
                'count': item['count'],
                'room_count': item['room_count'],
            })

        by_room = list(
            qs.exclude(room='')
            .values('building', 'room')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
            )
            .order_by('-total_cost')[:50]
        )
        rooms = []
        for item in by_room:
            rooms.append({
                'building': item['building'] or '(未设置)',
                'room': item['room'],
                'label': f"{item['building'] or ''} {item['room']}".strip(),
                'total_cost': BIAnalyticsService._decimal_to_float(item['total_cost']),
                'total_usage': BIAnalyticsService._decimal_to_float(item['total_usage']),
                'count': item['count'],
            })

        no_space_count = qs.filter(Q(building='') & Q(room='')).count()

        return {
            'buildings': buildings,
            'rooms': rooms,
            'summary': {
                'building_count': len(buildings),
                'room_count': len(rooms),
                'no_space_count': no_space_count,
            },
        }

    @staticmethod
    def by_time_period(filters: dict, user: Optional[User] = None) -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)

        hour = ExtractHour('created_at')
        period_expr = Case(
            When(hour__gte=6, hour__lt=12, then=Value(BIAnalyticsService.TIME_PERIOD_MORNING)),
            When(hour__gte=12, hour__lt=18, then=Value(BIAnalyticsService.TIME_PERIOD_NOON)),
            When(hour__gte=18, hour__lt=24, then=Value(BIAnalyticsService.TIME_PERIOD_EVENING)),
            default=Value(BIAnalyticsService.TIME_PERIOD_NIGHT),
            output_field=CharField(),
        )

        stats = list(
            qs.annotate(period=period_expr)
            .values('period')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
                water_cost=Coalesce(
                    Sum(Case(When(category='water', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
                electricity_cost=Coalesce(
                    Sum(Case(When(category='electricity', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
            )
            .order_by('period')
        )

        label_map = dict(BIAnalyticsService.TIME_PERIOD_CHOICES)
        period_order = [
            BIAnalyticsService.TIME_PERIOD_MORNING,
            BIAnalyticsService.TIME_PERIOD_NOON,
            BIAnalyticsService.TIME_PERIOD_EVENING,
            BIAnalyticsService.TIME_PERIOD_NIGHT,
        ]
        stats_by_period = {item['period']: item for item in stats}

        grand_total = BIAnalyticsService._decimal_to_float(
            qs.aggregate(total=Sum('cost_amount'))['total'] or 0
        )
        data = []
        for p in period_order:
            item = stats_by_period.get(p, {})
            total = BIAnalyticsService._decimal_to_float(item.get('total_cost', 0))
            data.append({
                'period': p,
                'period_label': label_map.get(p, p),
                'total_cost': total,
                'total_usage': BIAnalyticsService._decimal_to_float(item.get('total_usage', 0)),
                'count': item.get('count', 0),
                'water_cost': BIAnalyticsService._decimal_to_float(item.get('water_cost', 0)),
                'electricity_cost': BIAnalyticsService._decimal_to_float(item.get('electricity_cost', 0)),
                'percentage': round(total / grand_total * 100, 2) if grand_total > 0 else 0,
            })

        peak_period = max(data, key=lambda x: x['total_cost']) if data else None
        return {
            'data': data,
            'items': data,
            'summary': {
                'grand_total': grand_total,
                'peak_period': peak_period['period'] if peak_period else None,
                'peak_period_label': peak_period['period_label'] if peak_period else None,
            },
        }

    @staticmethod
    def compare_periods(
        filters_a: dict,
        filters_b: dict,
        user: Optional[User] = None,
        granularity: str = 'day',
    ) -> dict:
        trend_a = BIAnalyticsService.by_time_trend(filters_a, user, granularity)
        trend_b = BIAnalyticsService.by_time_trend(filters_b, user, granularity)

        total_a = trend_a['summary']['total_cost']
        total_b = trend_b['summary']['total_cost']
        count_a = trend_a['summary']['record_count']
        count_b = trend_b['summary']['record_count']

        map_a = {item['period']: item for item in trend_a['data']}
        map_b = {item['period']: item for item in trend_b['data']}
        all_periods = sorted(set(list(map_a.keys()) + list(map_b.keys())))

        comparison = []
        for period in all_periods:
            a = map_a.get(period, {'total_cost': 0, 'count': 0})
            b = map_b.get(period, {'total_cost': 0, 'count': 0})
            comparison.append({
                'period': period,
                'period_a_cost': a['total_cost'],
                'period_b_cost': b['total_cost'],
                'period_a_count': a.get('count', 0),
                'period_b_count': b.get('count', 0),
                'cost_growth_rate': BIAnalyticsService._calc_growth_rate(b['total_cost'], a['total_cost']),
            })

        return {
            'period_a': {
                'start_date': str(filters_a.get('start_date', '')) if filters_a.get('start_date') else '',
                'end_date': str(filters_a.get('end_date', '')) if filters_a.get('end_date') else '',
                'total_cost': total_a,
                'record_count': count_a,
            },
            'period_b': {
                'start_date': str(filters_b.get('start_date', '')) if filters_b.get('start_date') else '',
                'end_date': str(filters_b.get('end_date', '')) if filters_b.get('end_date') else '',
                'total_cost': total_b,
                'record_count': count_b,
            },
            'growth_rate': BIAnalyticsService._calc_growth_rate(total_b, total_a),
            'count_growth_rate': BIAnalyticsService._calc_growth_rate(count_b, count_a),
            'comparison': comparison,
        }

    @staticmethod
    def by_weekday(filters: dict, user: Optional[User] = None) -> dict:
        qs = BIAnalyticsService._build_base_queryset(filters, user)

        weekday_expr = ExtractWeekDay('created_at')

        stats = list(
            qs.annotate(weekday=weekday_expr)
            .values('weekday')
            .annotate(
                total_cost=Coalesce(Sum('cost_amount'), Value(0)),
                total_usage=Coalesce(Sum('usage'), Value(0)),
                count=Count('id'),
                water_cost=Coalesce(
                    Sum(Case(When(category='water', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
                electricity_cost=Coalesce(
                    Sum(Case(When(category='electricity', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                    Value(0),
                ),
            )
            .order_by('weekday')
        )

        weekday_labels = {
            1: '周一',
            2: '周二',
            3: '周三',
            4: '周四',
            5: '周五',
            6: '周六',
            7: '周日',
        }

        grand_total = BIAnalyticsService._decimal_to_float(
            qs.aggregate(total=Sum('cost_amount'))['total'] or 0
        )
        stats_map = {s['weekday']: s for s in stats}
        data = []
        for dow in range(1, 8):
            item = stats_map.get(dow, {})
            total = BIAnalyticsService._decimal_to_float(item.get('total_cost', 0))
            data.append({
                'weekday': dow,
                'weekday_label': weekday_labels[dow],
                'total_cost': total,
                'total_usage': BIAnalyticsService._decimal_to_float(item.get('total_usage', 0)),
                'count': item.get('count', 0),
                'water_cost': BIAnalyticsService._decimal_to_float(item.get('water_cost', 0)),
                'electricity_cost': BIAnalyticsService._decimal_to_float(item.get('electricity_cost', 0)),
                'percentage': round(total / grand_total * 100, 2) if grand_total > 0 else 0,
            })

        peak = max(data, key=lambda x: x['total_cost']) if data else None
        return {
            'data': data,
            'items': data,
            'summary': {
                'grand_total': grand_total,
                'peak_weekday': peak['weekday'] if peak else None,
                'peak_weekday_label': peak['weekday_label'] if peak else None,
            },
        }

    @staticmethod
    def student_profile(user: User) -> dict:
        qs = ConsumptionRecord.objects.filter(user=user)

        total = qs.aggregate(
            total_cost=Coalesce(Sum('cost_amount'), Value(0)),
            water_cost=Coalesce(
                Sum(Case(When(category='water', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                Value(0),
            ),
            electricity_cost=Coalesce(
                Sum(Case(When(category='electricity', then=F('cost_amount')), default=Value(0), output_field=DecimalField())),
                Value(0),
            ),
            total_count=Count('id'),
        )
        total_cost = BIAnalyticsService._decimal_to_float(total['total_cost'])
        water_cost = BIAnalyticsService._decimal_to_float(total['water_cost'])
        electricity_cost = BIAnalyticsService._decimal_to_float(total['electricity_cost'])

        period_stats = BIAnalyticsService.by_time_period({}, user)
        peak_period = period_stats['summary'].get('peak_period')
        peak_period_label = period_stats['summary'].get('peak_period_label')

        today = date.today()
        six_months_ago = today - timedelta(days=180)
        monthly_filters = {'start_date': six_months_ago, 'end_date': today}
        monthly_trend = BIAnalyticsService.by_time_trend(monthly_filters, user, 'month')

        avg_monthly = 0.0
        if monthly_trend['data']:
            avg_monthly = round(
                sum(m['total_cost'] for m in monthly_trend['data']) / len(monthly_trend['data']),
                2,
            )

        return {
            'category_breakdown': {
                'water': {
                    'cost': water_cost,
                    'percentage': round(water_cost / total_cost * 100, 2) if total_cost > 0 else 0,
                },
                'electricity': {
                    'cost': electricity_cost,
                    'percentage': round(electricity_cost / total_cost * 100, 2) if total_cost > 0 else 0,
                },
                'total_cost': total_cost,
                'total_count': total['total_count'] or 0,
            },
            'peak_period': peak_period,
            'peak_period_label': peak_period_label,
            'time_period_distribution': period_stats['data'],
            'monthly_trend': monthly_trend['data'],
            'summary': {
                'avg_monthly_cost': avg_monthly,
                'total_cost': total_cost,
            },
        }

    @staticmethod
    def get_dimension_options(user: Optional[User] = None) -> dict:
        role = getattr(getattr(user, 'profile', None), 'role', Profile.ROLE_STUDENT)
        qs = ConsumptionRecord.objects.all()
        if role != Profile.ROLE_ADMIN:
            qs = qs.filter(user=user)

        buildings = sorted([b for b in qs.exclude(building='').values_list('building', flat=True).distinct() if b])
        rooms = sorted([r for r in qs.exclude(room='').values_list('room', flat=True).distinct() if r])

        date_range = qs.aggregate(
            min_date=Min('created_at'),
            max_date=Max('created_at'),
        )

        return {
            'categories': [
                {'value': v, 'label': l} for v, l in ConsumptionRecord.CATEGORY_CHOICES
            ],
            'channels': [
                {'value': v, 'label': l} for v, l in ConsumptionRecord.CHANNEL_CHOICES
            ],
            'buildings': [{'value': b, 'label': b} for b in buildings],
            'rooms': [{'value': r, 'label': r} for r in rooms],
            'date_range': {
                'min': date_range['min_date'].strftime('%Y-%m-%d') if date_range['min_date'] else None,
                'max': date_range['max_date'].strftime('%Y-%m-%d') if date_range['max_date'] else None,
            },
        }
