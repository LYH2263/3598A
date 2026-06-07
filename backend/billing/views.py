import csv
import io
from datetime import datetime

from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import IsAdminRole
from billing.models import (
    BalanceChangeLog,
    ConsumptionRecord,
    MonthlyStatement,
    RechargeOrder,
    RechargeRecord,
    ReconciliationDiff,
    SettlementRun,
    Wallet,
)
from billing.serializers import (
    BalanceChangeLogSerializer,
    ConsumptionCreateSerializer,
    ConsumptionRecordSerializer,
    CrossMonthAdjustSerializer,
    MonthlyStatementSerializer,
    RechargeCreateSerializer,
    RechargeOrderBatchReviewSerializer,
    RechargeOrderCreateSerializer,
    RechargeOrderReviewSerializer,
    RechargeOrderSerializer,
    RechargeRecordSerializer,
    ReconciliationDiffSerializer,
    RunSettlementSerializer,
    SettlementRunSerializer,
    StatementActionSerializer,
    WalletActionSerializer,
    WalletSerializer,
)
from billing.services.ledger_service import LedgerService
from billing.services.monthly_closing_service import MonthlyClosingService


class DashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        wallet, _ = Wallet.objects.get_or_create(user=user)

        recharge_total = user.recharges.aggregate(total=Sum('amount')).get('total') or 0
        consumption_total = user.consumptions.aggregate(total=Sum('cost_amount')).get('total') or 0

        recharges = RechargeRecord.objects.filter(user=user)[:5]
        consumptions = ConsumptionRecord.objects.filter(user=user)[:5]
        pending_orders = RechargeOrder.objects.filter(user=user, status=RechargeOrder.STATUS_PENDING).count()

        return Response(
            {
                'wallet': WalletSerializer(wallet).data,
                'summary': {
                    'total_recharge': recharge_total,
                    'total_consumption': consumption_total,
                    'pending_recharge_orders': pending_orders,
                },
                'recent_recharges': RechargeRecordSerializer(recharges, many=True).data,
                'recent_consumptions': ConsumptionRecordSerializer(consumptions, many=True).data,
            }
        )


class RechargeListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role == Profile.ROLE_ADMIN:
            return RechargeRecord.objects.select_related('user').all()
        return RechargeRecord.objects.select_related('user').filter(user=request.user)

    def get(self, request):
        queryset = self.get_queryset(request)[:100]
        return Response(RechargeRecordSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = RechargeCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(RechargeRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class RechargeOrderListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        queryset = RechargeOrder.objects.select_related('user', 'reviewer')
        if role == Profile.ROLE_ADMIN:
            return queryset.all()
        return queryset.filter(user=request.user)

    def get(self, request):
        queryset = self.get_queryset(request)
        status_filter = request.query_params.get('status', '').strip()
        user_id = request.query_params.get('user_id', '').strip()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if user_id and getattr(request.user.profile, 'role', '') == Profile.ROLE_ADMIN:
            queryset = queryset.filter(user_id=user_id)

        return Response(RechargeOrderSerializer(queryset[:200], many=True).data)

    def post(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role != Profile.ROLE_STUDENT:
            return Response({'detail': '仅学生可提交充值订单。'}, status=status.HTTP_403_FORBIDDEN)

        serializer = RechargeOrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(RechargeOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class RechargeOrderReviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, order_id: int):
        order = RechargeOrder.objects.filter(id=order_id).first()
        if not order:
            return Response({'detail': '充值订单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RechargeOrderReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reviewed_order = LedgerService.review_recharge_order(
            order=order,
            action=serializer.validated_data['action'],
            reviewer=request.user,
            review_remark=serializer.validated_data.get('review_remark', ''),
        )
        return Response(RechargeOrderSerializer(reviewed_order).data)


class RechargeOrderBatchReviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = RechargeOrderBatchReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = LedgerService.batch_review_recharge_orders(
            order_ids=serializer.validated_data['order_ids'],
            action=serializer.validated_data['action'],
            reviewer=request.user,
            review_remark=serializer.validated_data.get('review_remark', ''),
        )
        return Response(result)


class ConsumptionListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        queryset = ConsumptionRecord.objects.select_related('user').all()
        if role != Profile.ROLE_ADMIN:
            queryset = queryset.filter(user=request.user)

        category = request.query_params.get('category', '').strip()
        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        user_id = request.query_params.get('user_id', '').strip()

        if category:
            queryset = queryset.filter(category=category)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if user_id and role == Profile.ROLE_ADMIN:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    def get(self, request):
        queryset = self.get_queryset(request)[:200]
        return Response(ConsumptionRecordSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = ConsumptionCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(ConsumptionRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class ConsumptionStatsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        queryset = ConsumptionRecord.objects.all()
        if role != Profile.ROLE_ADMIN:
            queryset = queryset.filter(user=request.user)

        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        user_id = request.query_params.get('user_id', '').strip()

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if user_id and role == Profile.ROLE_ADMIN:
            queryset = queryset.filter(user_id=user_id)

        category_stats = (
            queryset.values('category')
            .annotate(total_cost=Sum('cost_amount'), total_usage=Sum('usage'), count=Count('id'))
            .order_by('category')
        )

        trend = (
            queryset.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total_cost=Sum('cost_amount'))
            .order_by('day')
        )

        return Response(
            {
                'category_stats': list(category_stats),
                'daily_trend': [
                    {
                        'day': item['day'].strftime('%Y-%m-%d') if item['day'] else '',
                        'total_cost': item['total_cost'] or 0,
                    }
                    for item in trend
                ],
            }
        )


class WalletActionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, user_id: int):
        target_user = User.objects.filter(id=user_id).first()
        if not target_user:
            return Response({'detail': '用户不存在。'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WalletActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')

        if action == 'freeze':
            wallet = LedgerService.freeze_wallet(target_user, request.user.username, reason)
        else:
            wallet = LedgerService.unfreeze_wallet(target_user, request.user.username, reason)

        return Response({'wallet': WalletSerializer(wallet).data})


class WalletLogListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        queryset = BalanceChangeLog.objects.select_related('user')

        if role != Profile.ROLE_ADMIN:
            queryset = queryset.filter(user=request.user)

        user_id = request.query_params.get('user_id', '').strip()
        change_type = request.query_params.get('change_type', '').strip()
        settlement_period = request.query_params.get('settlement_period', '').strip()
        if user_id and role == Profile.ROLE_ADMIN:
            queryset = queryset.filter(user_id=user_id)
        if change_type:
            queryset = queryset.filter(change_type=change_type)
        if settlement_period:
            queryset = queryset.filter(settlement_period=settlement_period)

        return Response(BalanceChangeLogSerializer(queryset[:300], many=True).data)


# ============= 月结管理（管理员） =============

class MonthlyStatementAdminListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        period = request.query_params.get('period', '').strip()
        user_id = request.query_params.get('user_id', '').strip()
        status = request.query_params.get('status', '').strip()

        queryset = MonthlyStatement.objects.select_related('user').all()
        if period:
            queryset = queryset.filter(period=period)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if status:
            queryset = queryset.filter(status=status)

        return Response(MonthlyStatementSerializer(queryset[:500], many=True).data)


class MonthlyStatementAdminDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, statement_id: int):
        stmt = MonthlyStatement.objects.select_related('user').filter(pk=statement_id).first()
        if not stmt:
            return Response({'detail': '月结单不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MonthlyStatementSerializer(stmt).data)

    def post(self, request, statement_id: int):
        stmt = MonthlyStatement.objects.filter(pk=statement_id).first()
        if not stmt:
            return Response({'detail': '月结单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StatementActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']

        try:
            if action == 'publish':
                stmt = MonthlyClosingService.publish_statement(stmt, request.user.username)
            else:
                stmt = MonthlyClosingService.rollback_statement(stmt, request.user.username)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MonthlyStatementSerializer(stmt).data)


class SettlementRunAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        runs = SettlementRun.objects.all()[:100]
        return Response(SettlementRunSerializer(runs, many=True).data)

    def post(self, request):
        serializer = RunSettlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period = serializer.validated_data['period']
        auto_publish = serializer.validated_data.get('auto_publish', True)
        user_id = serializer.validated_data.get('user_id')

        run = MonthlyClosingService.run_monthly_settlement(
            period=period,
            operator=request.user.username,
            auto_publish=auto_publish,
            user_id=user_id,
        )
        return Response(SettlementRunSerializer(run).data, status=status.HTTP_201_CREATED)


class ReconciliationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        run_id = request.query_params.get('run_id', '').strip()
        queryset = ReconciliationDiff.objects.select_related('user')
        if run_id:
            queryset = queryset.filter(run_id=run_id)
        return Response(ReconciliationDiffSerializer(queryset[:500], many=True).data)

    def post(self, request):
        result = MonthlyClosingService.run_reconciliation(operator=request.user.username)
        return Response(result)


class CrossMonthAdjustAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = CrossMonthAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = User.objects.filter(pk=serializer.validated_data['user_id']).first()
        if not target_user:
            return Response({'detail': '用户不存在。'}, status=status.HTTP_404_NOT_FOUND)

        try:
            log = MonthlyClosingService.apply_cross_month_adjustment(
                user=target_user,
                source_period=serializer.validated_data['source_period'],
                target_period=serializer.validated_data['target_period'],
                amount=serializer.validated_data['amount'],
                operator=request.user.username,
                remark=serializer.validated_data.get('remark', ''),
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(BalanceChangeLogSerializer(log).data, status=status.HTTP_201_CREATED)


# ============= 学生端：我的账单 =============

class StudentStatementListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        statements = MonthlyStatement.objects.filter(user=request.user).order_by('-period')
        return Response(MonthlyStatementSerializer(statements, many=True).data)


class StudentStatementDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, period: str):
        stmt = MonthlyStatement.objects.filter(
            user=request.user, period=period
        ).first()
        if not stmt:
            return Response({'detail': '该月度账单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        start, end = _period_start_end(period)
        logs = BalanceChangeLog.objects.filter(
            user=request.user,
            created_at__gte=start,
            created_at__lt=end,
        ).order_by('created_at')

        return Response({
            'statement': MonthlyStatementSerializer(stmt).data,
            'logs': BalanceChangeLogSerializer(logs, many=True).data,
        })


class StudentStatementDownloadCSVAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, period: str):
        stmt = MonthlyStatement.objects.filter(
            user=request.user, period=period
        ).first()
        if not stmt:
            return Response({'detail': '该月度账单不存在。'}, status=status.HTTP_404_NOT_FOUND)

        start, end = _period_start_end(period)
        logs = BalanceChangeLog.objects.filter(
            user=request.user,
            created_at__gte=start,
            created_at__lt=end,
        ).order_by('created_at')

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['学生水电充值月结单'])
        writer.writerow(['用户', request.user.username])
        writer.writerow(['账期', period])
        writer.writerow([])
        writer.writerow(['项目', '金额(元)', '笔数'])
        writer.writerow(['期初余额', str(stmt.opening_balance), ''])
        writer.writerow(['本月充值', str(stmt.recharge_total), stmt.recharge_count])
        writer.writerow(['本月水费', str(stmt.water_total), stmt.water_count])
        writer.writerow(['本月电费', str(stmt.electricity_total), stmt.electricity_count])
        writer.writerow(['本月退款', str(stmt.refund_total), stmt.refund_count])
        writer.writerow(['本月调整', str(stmt.adjust_total), stmt.adjust_count])
        writer.writerow(['跨月调整', str(stmt.cross_month_adjust_total), ''])
        writer.writerow(['期末余额', str(stmt.closing_balance), ''])
        writer.writerow([])
        writer.writerow(['流水明细'])
        writer.writerow(['时间', '类型', '变动金额', '变动前余额', '变动后余额', '操作人', '备注', '是否已结账'])

        type_label = dict(BalanceChangeLog.CHANGE_TYPE_CHOICES)
        for log in logs:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                type_label.get(log.change_type, log.change_type),
                str(log.amount_delta),
                str(log.balance_before),
                str(log.balance_after),
                log.operator,
                log.remark,
                '是' if log.is_settled else '否',
            ])

        response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="statement_{request.user.username}_{period}.csv"'
        return response


def _period_start_end(period: str):
    from django.utils import timezone as tz
    year, month = map(int, period.split('-'))
    start = datetime(year, month, 1, 0, 0, 0)
    if month == 12:
        ny, nm = year + 1, 1
    else:
        ny, nm = year, month + 1
    end = datetime(ny, nm, 1, 0, 0, 0)
    current_tz = tz.get_current_timezone()
    return current_tz.localize(start), current_tz.localize(end)
