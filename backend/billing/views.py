import csv
import io
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import IsAdminRole
from billing.models import (
    BalanceChangeLog,
    ConsumptionRecord,
    DashboardPreference,
    MonthlyStatement,
    PlanExecution,
    PriceStrategy,
    RechargeOrder,
    RechargePlan,
    RechargeRecord,
    ReconciliationDiff,
    SettlementRun,
    Wallet,
)
from billing.serializers import (
    BIFilterSerializer,
    BICompareSerializer,
    BalanceChangeLogSerializer,
    ConsumptionCreateSerializer,
    ConsumptionRecordSerializer,
    CrossMonthAdjustSerializer,
    DashboardPreferenceSaveSerializer,
    DashboardPreferenceSerializer,
    MonthlyStatementSerializer,
    PlanActionSerializer,
    PlanExecutionSerializer,
    PricePreviewSerializer,
    PriceStrategySerializer,
    RechargeCreateSerializer,
    RechargeOrderBatchReviewSerializer,
    RechargeOrderCreateSerializer,
    RechargeOrderReviewSerializer,
    RechargeOrderSerializer,
    RechargePlanCreateSerializer,
    RechargePlanSerializer,
    RechargeRecordSerializer,
    ReconciliationDiffSerializer,
    RunSettlementSerializer,
    SettlementRunSerializer,
    StatementActionSerializer,
    WalletActionSerializer,
    WalletSerializer,
)
from billing.services.bi_analytics_service import BIAnalyticsService
from billing.services.ledger_service import LedgerService
from billing.services.monthly_closing_service import (
    MonthlyClosingService,
    _period_start_end as _mcs_period_start_end,
)


def _period_start_end(period):
    return _mcs_period_start_end(period)
from billing.services.pricing_service import PricingService
from billing.services.recharge_plan_service import RechargePlanService


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


class StudentStatementDownloadPDFAPIView(APIView):
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

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            return Response(
                {'detail': '服务器未安装 reportlab，无法生成 PDF，请使用 CSV 下载。'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        except Exception:
            pass

        import io as _io
        buf = _io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title=f'月结单_{request.user.username}_{period}',
        )

        font_name = 'STSong-Light'
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'zh_title', parent=styles['Title'], fontName=font_name, fontSize=20, leading=28
        )
        normal_style = ParagraphStyle(
            'zh_normal', parent=styles['Normal'], fontName=font_name, fontSize=11, leading=18
        )
        small_style = ParagraphStyle(
            'zh_small', parent=styles['Normal'], fontName=font_name, fontSize=9, leading=13
        )

        story = []
        story.append(Paragraph('学生水电充值月结单', title_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f'用户：{request.user.username} &nbsp;&nbsp; 账期：{period}', normal_style))
        story.append(Paragraph(f'生成时间：{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}', normal_style))
        story.append(Spacer(1, 14))

        summary_data = [
            ['项目', '金额（元）', '笔数'],
            ['期初余额', f'{stmt.opening_balance}', ''],
            ['本月充值', f'{stmt.recharge_total}', str(stmt.recharge_count)],
            ['本月水费', f'{stmt.water_total}', str(stmt.water_count)],
            ['本月电费', f'{stmt.electricity_total}', str(stmt.electricity_count)],
            ['本月退款', f'{stmt.refund_total}', str(stmt.refund_count)],
            ['本月调整', f'{stmt.adjust_total}', str(stmt.adjust_count)],
            ['跨月调整', f'{stmt.cross_month_adjust_total}', ''],
            ['期末余额', f'{stmt.closing_balance}', ''],
        ]
        summary_table = Table(summary_data, colWidths=[55 * mm, 40 * mm, 30 * mm])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef4ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f4ed3')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafbff')]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 18))

        story.append(Paragraph('流水明细', normal_style))
        story.append(Spacer(1, 8))

        type_label = dict(BalanceChangeLog.CHANGE_TYPE_CHOICES)
        log_header = ['时间', '类型', '变动金额', '变动前', '变动后', '操作人', '备注', '已结账']
        log_data = [log_header]
        for log in logs:
            log_data.append([
                log.created_at.strftime('%Y-%m-%d %H:%M'),
                type_label.get(log.change_type, log.change_type),
                f'{log.amount_delta}',
                f'{log.balance_before}',
                f'{log.balance_after}',
                log.operator or '',
                (log.remark or '')[:30],
                '是' if log.is_settled else '否',
            ])
        if len(log_data) == 1:
            log_data.append(['(无流水记录)', '', '', '', '', '', '', ''])

        log_table = Table(log_data, colWidths=[28 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 16 * mm, 30 * mm, 16 * mm])
        log_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef4ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f4ed3')),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafbff')]),
        ]))
        story.append(log_table)
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            '本账单由系统自动生成，如有疑问请联系管理员。',
            small_style,
        ))

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="statement_{request.user.username}_{period}.pdf"'
        return response


def _parse_filters_from_request(request, serializer_class=BIFilterSerializer):
    data = {}
    for key in request.query_params:
        val = request.query_params.getlist(key) if key.endswith('[]') or key in {
            'user_ids', 'categories', 'channels', 'buildings', 'rooms'
        } else request.query_params.get(key)
        if key.endswith('[]'):
            data[key[:-2]] = val
        else:
            data[key] = val
    if isinstance(data.get('user_ids'), str):
        data['user_ids'] = [int(x) for x in data['user_ids'].split(',') if x.strip()]
    if isinstance(data.get('categories'), str):
        data['categories'] = [x for x in data['categories'].split(',') if x.strip()]
    if isinstance(data.get('channels'), str):
        data['channels'] = [x for x in data['channels'].split(',') if x.strip()]
    if isinstance(data.get('buildings'), str):
        data['buildings'] = [x for x in data['buildings'].split(',') if x.strip()]
    if isinstance(data.get('rooms'), str):
        data['rooms'] = [x for x in data['rooms'].split(',') if x.strip()]
    for k in list(data.keys()):
        if data[k] in ('', None):
            del data[k]
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


# ============= BI 分析（管理员/学生共用，权限内数据） =============

class BIOverviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        by_category = BIAnalyticsService.by_category(filters, request.user)
        by_trend = BIAnalyticsService.by_time_trend(
            filters, request.user, filters.get('trend_granularity', 'day')
        )
        by_channel = BIAnalyticsService.by_channel(filters, request.user)
        top_res = BIAnalyticsService.top_students(
            filters, request.user, filters.get('top_n', 10)
        )
        by_building_room = BIAnalyticsService.by_building_room(filters, request.user)
        by_time_period = BIAnalyticsService.by_time_period(filters, request.user)
        by_weekday = BIAnalyticsService.by_weekday(filters, request.user)
        return Response({
            'by_category': by_category,
            'by_trend': by_trend,
            'by_channel': by_channel,
            'top_students': top_res.get('data', []),
            'by_building_room': by_building_room,
            'by_time_period': by_time_period,
            'by_weekday': by_weekday,
            'dimension_options': BIAnalyticsService.get_dimension_options(request.user),
        })


class BICategoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        return Response(BIAnalyticsService.by_category(filters, request.user))


class BITrendAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        granularity = filters.get('trend_granularity', 'day')
        return Response(BIAnalyticsService.by_time_trend(filters, request.user, granularity))


class BIChannelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        return Response(BIAnalyticsService.by_channel(filters, request.user))


class BITopStudentsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        top_n = filters.get('top_n', 10)
        return Response(BIAnalyticsService.top_students(filters, request.user, top_n))


class BIBuildingRoomAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        return Response(BIAnalyticsService.by_building_room(filters, request.user))


class BITimePeriodAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        return Response(BIAnalyticsService.by_time_period(filters, request.user))


class BIWeekdayAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = _parse_filters_from_request(request)
        return Response(BIAnalyticsService.by_weekday(filters, request.user))


class BICompareAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        valid = _parse_filters_from_request(request, BICompareSerializer)
        filters_a = {
            'start_date': valid.get('start_date'),
            'end_date': valid.get('end_date'),
            'user_ids': valid.get('user_ids', []),
            'categories': valid.get('categories', []),
            'channels': valid.get('channels', []),
            'min_amount': valid.get('min_amount'),
            'max_amount': valid.get('max_amount'),
            'buildings': valid.get('buildings', []),
            'rooms': valid.get('rooms', []),
        }
        filters_b = {
            'start_date': valid.get('compare_start_date'),
            'end_date': valid.get('compare_end_date'),
            'user_ids': valid.get('user_ids', []),
            'categories': valid.get('categories', []),
            'channels': valid.get('channels', []),
            'min_amount': valid.get('min_amount'),
            'max_amount': valid.get('max_amount'),
            'buildings': valid.get('buildings', []),
            'rooms': valid.get('rooms', []),
        }
        granularity = valid.get('trend_granularity', 'day')
        return Response(
            BIAnalyticsService.compare_periods(filters_a, filters_b, request.user, granularity)
        )


class BIDimensionOptionsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(BIAnalyticsService.get_dimension_options(request.user))


class BIExportCSVAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    VIEW_CHOICES = {
        'category', 'trend', 'channel', 'top_students', 'building_room', 'time_period', 'weekday', 'my_profile',
    }

    def get(self, request, view_name: str = ''):
        if not view_name:
            view_name = request.query_params.get('view', '')
        if view_name not in self.VIEW_CHOICES:
            return Response({'detail': '未知的视图类型。'}, status=status.HTTP_400_BAD_REQUEST)

        filters = _parse_filters_from_request(request)
        buf = io.StringIO()
        writer = csv.writer(buf)

        if view_name == 'category':
            result = BIAnalyticsService.by_category(filters, request.user)
            writer.writerow(['消费分类统计'])
            writer.writerow(['类目', '消费金额(元)', '用量', '笔数', '平均金额(元)', '占比(%)'])
            for row in result['data']:
                writer.writerow([
                    row['category_label'],
                    f"{row['total_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                    f"{row['avg_cost']:.2f}",
                    f"{row['percentage']:.2f}",
                ])
            writer.writerow([])
            writer.writerow(['合计', f"{result['summary']['grand_total']:.2f}", '', result['summary']['record_count'], '', '100.00'])
            filename = f'category_stats'

        elif view_name == 'trend':
            granularity = filters.get('trend_granularity', 'day')
            result = BIAnalyticsService.by_time_trend(filters, request.user, granularity)
            writer.writerow([f'消费趋势（按{granularity}）'])
            writer.writerow(['周期', '消费金额(元)', '水费(元)', '电费(元)', '用量', '笔数'])
            for row in result['data']:
                writer.writerow([
                    row['period'],
                    f"{row['total_cost']:.2f}",
                    f"{row['water_cost']:.2f}",
                    f"{row['electricity_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                ])
            writer.writerow([])
            writer.writerow(['合计', f"{result['summary']['total_cost']:.2f}", '', '', f"{result['summary']['total_usage']:.2f}", result['summary']['record_count']])
            filename = f'trend_{granularity}'

        elif view_name == 'channel':
            result = BIAnalyticsService.by_channel(filters, request.user)
            writer.writerow(['消费渠道统计'])
            writer.writerow(['渠道', '消费金额(元)', '用量', '笔数', '占比(%)'])
            for row in result['data']:
                writer.writerow([
                    row['channel_label'],
                    f"{row['total_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                    f"{row['percentage']:.2f}",
                ])
            writer.writerow([])
            writer.writerow(['合计', f"{result['summary']['grand_total']:.2f}", '', '', '100.00'])
            filename = 'channel_stats'

        elif view_name == 'top_students':
            top_n = filters.get('top_n', 10)
            result = BIAnalyticsService.top_students(filters, request.user, top_n)
            writer.writerow([f'学生消费 Top {top_n}'])
            writer.writerow(['排名', '用户ID', '用户名', '学号', '消费金额(元)', '水费(元)', '电费(元)', '用量', '笔数'])
            for row in result['data']:
                writer.writerow([
                    row['rank'],
                    row['user_id'],
                    row['username'],
                    row['student_id'],
                    f"{row['total_cost']:.2f}",
                    f"{row['water_cost']:.2f}",
                    f"{row['electricity_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                ])
            filename = f'top_{top_n}_students'

        elif view_name == 'building_room':
            result = BIAnalyticsService.by_building_room(filters, request.user)
            writer.writerow(['楼栋消费统计'])
            writer.writerow(['楼栋', '消费金额(元)', '用量', '笔数', '涉及房间数'])
            for row in result['buildings']:
                writer.writerow([
                    row['building'],
                    f"{row['total_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                    row['room_count'],
                ])
            writer.writerow([])
            writer.writerow(['房间消费统计'])
            writer.writerow(['楼栋', '房间', '消费金额(元)', '用量', '笔数'])
            for row in result['rooms']:
                writer.writerow([
                    row['building'],
                    row['room'],
                    f"{row['total_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                ])
            filename = 'building_room_stats'

        elif view_name == 'time_period':
            result = BIAnalyticsService.by_time_period(filters, request.user)
            writer.writerow(['消费时段分布'])
            writer.writerow(['时段', '消费金额(元)', '水费(元)', '电费(元)', '用量', '笔数', '占比(%)'])
            for row in result['data']:
                writer.writerow([
                    row['period_label'],
                    f"{row['total_cost']:.2f}",
                    f"{row['water_cost']:.2f}",
                    f"{row['electricity_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                    f"{row['percentage']:.2f}",
                ])
            filename = 'time_period_stats'

        elif view_name == 'weekday':
            result = BIAnalyticsService.by_weekday(filters, request.user)
            writer.writerow(['按星期分布'])
            writer.writerow(['星期', '消费金额(元)', '水费(元)', '电费(元)', '用量', '笔数', '占比(%)'])
            for row in result['data']:
                writer.writerow([
                    row['weekday_label'],
                    f"{row['total_cost']:.2f}",
                    f"{row['water_cost']:.2f}",
                    f"{row['electricity_cost']:.2f}",
                    f"{row['total_usage']:.2f}",
                    row['count'],
                    f"{row['percentage']:.2f}",
                ])
            writer.writerow([])
            writer.writerow(['合计', f"{result['summary']['grand_total']:.2f}", '', '', '', '', '100.00'])
            filename = 'weekday_stats'

        else:  # my_profile
            result = BIAnalyticsService.student_profile(request.user)
            writer.writerow(['我的消费分析'])
            writer.writerow(['累计消费(元)', '月均消费(元)', '消费笔数', '高峰时段'])
            writer.writerow([
                f"{result['summary']['total_cost']:.2f}",
                f"{result['summary']['avg_monthly_cost']:.2f}",
                result['category_breakdown']['total_count'],
                result.get('peak_period_label') or '',
            ])
            writer.writerow([])
            writer.writerow(['类目占比'])
            writer.writerow(['类目', '金额(元)', '占比(%)'])
            writer.writerow([
                '水费',
                f"{result['category_breakdown']['water']['cost']:.2f}",
                f"{result['category_breakdown']['water']['percentage']:.2f}",
            ])
            writer.writerow([
                '电费',
                f"{result['category_breakdown']['electricity']['cost']:.2f}",
                f"{result['category_breakdown']['electricity']['percentage']:.2f}",
            ])
            writer.writerow([])
            writer.writerow(['近6个月趋势'])
            writer.writerow(['月份', '消费金额(元)', '笔数'])
            for row in result['monthly_trend']:
                writer.writerow([
                    row.get('period', ''),
                    f"{row['total_cost']:.2f}",
                    row.get('count', 0),
                ])
            filename = 'my_analytics'

        response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="bi_{filename}_{datetime.now().strftime("%Y%m%d")}.csv"'
        return response


# ============= 学生侧：我的分析 =============

class StudentProfileAnalyticsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(BIAnalyticsService.student_profile(request.user))


# ============= 看板偏好 =============

class DashboardPreferenceListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs = DashboardPreference.objects.filter(user=request.user)
        return Response(DashboardPreferenceSerializer(prefs, many=True).data)


class DashboardPreferenceDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, board_key: str):
        pref, _ = DashboardPreference.objects.get_or_create(
            user=request.user,
            board_key=board_key,
        )
        return Response(DashboardPreferenceSerializer(pref).data)

    def put(self, request, board_key: str):
        serializer = DashboardPreferenceSaveSerializer(data={**request.data, 'board_key': board_key})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pref, created = DashboardPreference.objects.update_or_create(
            user=request.user,
            board_key=board_key,
            defaults={
                'card_order': data.get('card_order', []),
                'collapsed_cards': data.get('collapsed_cards', []),
                'filters_snapshot': data.get('filters_snapshot', {}),
            },
        )
        return Response(DashboardPreferenceSerializer(pref).data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


# ============= 学生侧：我的充值计划 =============

class StudentRechargePlanListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role != Profile.ROLE_STUDENT:
            return Response({'detail': '仅学生可访问。'}, status=status.HTTP_403_FORBIDDEN)
        plans = RechargePlan.objects.filter(user=request.user).select_related('user')
        status_filter = request.query_params.get('status', '').strip()
        if status_filter:
            plans = plans.filter(status=status_filter)
        return Response(RechargePlanSerializer(plans, many=True).data)

    def post(self, request):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role != Profile.ROLE_STUDENT:
            return Response({'detail': '仅学生可创建充值计划。'}, status=status.HTTP_403_FORBIDDEN)
        serializer = RechargePlanCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response(RechargePlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class StudentRechargePlanDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_plan(self, request, plan_id: int):
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role == Profile.ROLE_ADMIN:
            return RechargePlan.objects.filter(id=plan_id).select_related('user').first()
        return RechargePlan.objects.filter(id=plan_id, user=request.user).select_related('user').first()

    def get(self, request, plan_id: int):
        plan = self._get_plan(request, plan_id)
        if not plan:
            return Response({'detail': '充值计划不存在。'}, status=status.HTTP_404_NOT_FOUND)
        executions = PlanExecution.objects.filter(plan=plan).order_by('-scheduled_date')[:100]
        return Response({
            'plan': RechargePlanSerializer(plan).data,
            'executions': PlanExecutionSerializer(executions, many=True).data,
        })

    def post(self, request, plan_id: int, action: str):
        plan = self._get_plan(request, plan_id)
        if not plan:
            return Response({'detail': '充值计划不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if getattr(request.user.profile, 'role', '') != Profile.ROLE_ADMIN and plan.user_id != request.user.id:
            return Response({'detail': '无权限操作。'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PlanActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', '')

        try:
            if action == 'pause':
                plan = RechargePlanService.pause_plan(plan, request.user, reason)
            elif action == 'resume':
                plan = RechargePlanService.resume_plan(plan)
            elif action == 'end':
                plan = RechargePlanService.end_plan(plan, reason)
            else:
                return Response({'detail': '不支持的操作。'}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response({'detail': str(e.detail)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(RechargePlanSerializer(plan).data)


class PlanUpcomingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 7))
        days = max(1, min(days, 30))
        role = getattr(request.user.profile, 'role', Profile.ROLE_STUDENT)
        if role == Profile.ROLE_ADMIN:
            user_id = request.query_params.get('user_id', '').strip()
            target_user = request.user
            if user_id:
                from django.contrib.auth.models import User
                target_user = User.objects.filter(id=user_id).first() or request.user
            upcoming = RechargePlanService.get_upcoming_executions(target_user, days)
        else:
            upcoming = RechargePlanService.get_upcoming_executions(request.user, days)
        return Response({'days': days, 'upcoming': upcoming})


# ============= 管理员侧：充值计划管理 =============

class AdminRechargePlanListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = RechargePlan.objects.select_related('user').all()
        status_filter = request.query_params.get('status', '').strip()
        user_id = request.query_params.get('user_id', '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return Response(RechargePlanSerializer(queryset[:500], many=True).data)


class AdminPlanExecutionListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = PlanExecution.objects.select_related('user', 'plan', 'order').all()
        status_filter = request.query_params.get('status', '').strip()
        user_id = request.query_params.get('user_id', '').strip()
        plan_id = request.query_params.get('plan_id', '').strip()
        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        if start_date:
            queryset = queryset.filter(scheduled_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_date__lte=end_date)

        return Response(PlanExecutionSerializer(queryset[:500], many=True).data)


# ============= 价格策略中心 =============


class PriceStrategyListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = PriceStrategy.objects.prefetch_related('tiers', 'timeslots').all()
        category = request.query_params.get('category', '').strip()
        scope_type = request.query_params.get('scope_type', '').strip()
        is_active = request.query_params.get('is_active', '').strip()

        if category:
            queryset = queryset.filter(category=category)
        if scope_type:
            queryset = queryset.filter(scope_type=scope_type)
        if is_active in ('true', 'false'):
            queryset = queryset.filter(is_active=(is_active == 'true'))

        return Response(PriceStrategySerializer(queryset.order_by('-priority', '-effective_from')[:500], many=True).data)

    def post(self, request):
        serializer = PriceStrategySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(PriceStrategySerializer(instance).data, status=status.HTTP_201_CREATED)


class PriceStrategyDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def _get(self, strategy_id: int):
        return PriceStrategy.objects.prefetch_related('tiers', 'timeslots').filter(id=strategy_id).first()

    def get(self, request, strategy_id: int):
        strategy = self._get(strategy_id)
        if not strategy:
            return Response({'detail': '价格策略不存在。'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PriceStrategySerializer(strategy).data)

    def put(self, request, strategy_id: int):
        strategy = self._get(strategy_id)
        if not strategy:
            return Response({'detail': '价格策略不存在。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PriceStrategySerializer(strategy, data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(PriceStrategySerializer(instance).data)

    def delete(self, request, strategy_id: int):
        strategy = self._get(strategy_id)
        if not strategy:
            return Response({'detail': '价格策略不存在。'}, status=status.HTTP_404_NOT_FOUND)
        strategy.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PricePreviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PricePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_user = None
        if data.get('user_id'):
            target_user = User.objects.filter(id=data['user_id']).first()
            if not target_user:
                return Response({'detail': '用户不存在。'}, status=status.HTTP_400_BAD_REQUEST)
        elif getattr(request.user.profile, 'role', '') != Profile.ROLE_ADMIN:
            target_user = request.user

        room = data.get('room')
        at_time = data.get('at_time') or timezone.now()
        compare_flag = str(request.data.get('compare', '')).lower() in ('1', 'true', 'yes', 'on')

        if compare_flag:
            result = PricingService.preview_compare(
                user=target_user,
                category=data['category'],
                usage=Decimal(data['usage']),
                at_time=at_time,
                room=room,
            )
            return Response(result)

        result = PricingService.preview(
            user=target_user,
            category=data['category'],
            usage=Decimal(data['usage']),
            at_time=at_time,
            room=room,
        )
        return Response(result.to_dict())
