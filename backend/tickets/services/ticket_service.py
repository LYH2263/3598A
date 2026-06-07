import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notices.services import NotificationService
from tickets.models import (
    Ticket,
    TicketAttachment,
    TicketEscalationLog,
    TicketReply,
    TicketSLAConfig,
)

logger = logging.getLogger(__name__)


class TicketService:
    DEFAULT_SLA = {
        Ticket.PRIORITY_URGENT: {'response_hours': 1, 'resolve_hours': 4},
        Ticket.PRIORITY_HIGH: {'response_hours': 2, 'resolve_hours': 12},
        Ticket.PRIORITY_NORMAL: {'response_hours': 4, 'resolve_hours': 24},
        Ticket.PRIORITY_LOW: {'response_hours': 8, 'resolve_hours': 72},
    }

    @staticmethod
    def _get_sla_config(priority: str) -> TicketSLAConfig | None:
        return TicketSLAConfig.objects.filter(priority=priority, is_active=True).first()

    @classmethod
    def _calculate_sla_deadline(cls, ticket: Ticket) -> timezone.datetime | None:
        cfg = cls._get_sla_config(ticket.priority)
        hours = cfg.resolve_hours if cfg else cls.DEFAULT_SLA[ticket.priority]['resolve_hours']
        return ticket.created_at + timedelta(hours=hours)

    @staticmethod
    def _notify_ticket_event(type_code: str, ticket: Ticket, user_ids: list[int], extra_vars: dict | None = None):
        try:
            variables = {
                'ticket_id': str(ticket.id),
                'ticket_title': ticket.title,
                'ticket_status': ticket.get_status_display(),
                'ticket_priority': ticket.get_priority_display(),
                'ticket_category': ticket.get_category_display(),
                'student_name': ticket.student.username if ticket.student else '',
            }
            if extra_vars:
                variables.update(extra_vars)
            NotificationService.dispatch(type_code=type_code, user_ids=user_ids, variables=variables)
        except Exception:
            logger.exception('Failed to send ticket notification for ticket #%s', ticket.id)

    @classmethod
    @transaction.atomic
    def create_ticket(
        cls,
        *,
        student: User,
        title: str,
        description: str,
        category: str,
        priority: str = Ticket.PRIORITY_NORMAL,
        room=None,
        room_text: str = '',
        contact_phone: str = '',
        attachments: list[dict] | None = None,
    ) -> Ticket:
        ticket = Ticket.objects.create(
            title=title.strip(),
            description=description.strip(),
            category=category,
            priority=priority,
            status=Ticket.STATUS_PENDING,
            student=student,
            room=room,
            room_text=room_text or '',
            contact_phone=contact_phone or '',
        )
        ticket.sla_deadline = cls._calculate_sla_deadline(ticket)
        ticket.save(update_fields=['sla_deadline'])

        if attachments:
            for att in attachments:
                TicketAttachment.objects.create(
                    ticket=ticket,
                    uploaded_by=student,
                    file_name=att.get('file_name', ''),
                    file_url=att.get('file_url', ''),
                    file_size=att.get('file_size', 0),
                    mime_type=att.get('mime_type', ''),
                )

        TicketReply.objects.create(
            ticket=ticket,
            author=student,
            content=description.strip(),
            action_type='create',
            action_detail={'initial': True},
        )

        admin_ids = list(
            User.objects.filter(profile__role='admin', is_active=True).values_list('id', flat=True)
        )
        if admin_ids:
            cls._notify_ticket_event('ticket_created', ticket, admin_ids)

        logger.info('Ticket #%s created by student %s', ticket.id, student.username)
        return ticket

    @classmethod
    @transaction.atomic
    def assign_ticket(cls, ticket: Ticket, assignee: User, operator: User) -> Ticket:
        if ticket.status not in (Ticket.STATUS_PENDING, Ticket.STATUS_ASSIGNED):
            raise ValueError(f'当前状态 {ticket.get_status_display()} 不可派单')

        if not hasattr(assignee, 'profile') or assignee.profile.role != 'admin':
            raise ValueError('处理人必须为管理员角色')

        old_assignee = ticket.assignee
        ticket.assignee = assignee
        ticket.status = Ticket.STATUS_ASSIGNED
        ticket.assigned_at = timezone.now()
        ticket.save(update_fields=['assignee', 'status', 'assigned_at', 'updated_at'])

        TicketReply.objects.create(
            ticket=ticket,
            author=operator,
            content=f'派单给 {assignee.username}',
            action_type='assign',
            action_detail={
                'from_assignee_id': old_assignee.id if old_assignee else None,
                'from_assignee_name': old_assignee.username if old_assignee else None,
                'to_assignee_id': assignee.id,
                'to_assignee_name': assignee.username,
            },
        )

        notify_ids = [assignee.id, ticket.student_id]
        if operator.id not in notify_ids:
            notify_ids.append(operator.id)
        cls._notify_ticket_event('ticket_assigned', ticket, notify_ids, {
            'assignee_name': assignee.username,
        })

        logger.info('Ticket #%s assigned to %s by %s', ticket.id, assignee.username, operator.username)
        return ticket

    @classmethod
    @transaction.atomic
    def start_processing(cls, ticket: Ticket, operator: User) -> Ticket:
        if ticket.status not in (Ticket.STATUS_ASSIGNED, Ticket.STATUS_WAITING_CONFIRM):
            raise ValueError(f'当前状态 {ticket.get_status_display()} 不可开始处理')

        if ticket.assignee and ticket.assignee_id != operator.id:
            if getattr(operator.profile, 'role', None) != 'admin':
                raise ValueError('只有被指派的处理人或管理员可开始处理')

        old_status = ticket.status
        ticket.status = Ticket.STATUS_PROCESSING
        if not ticket.started_at:
            ticket.started_at = timezone.now()
        ticket.save(update_fields=['status', 'started_at', 'updated_at'])

        TicketReply.objects.create(
            ticket=ticket,
            author=operator,
            content='开始处理工单',
            action_type='status_change',
            action_detail={'from_status': old_status, 'to_status': Ticket.STATUS_PROCESSING},
        )

        notify_ids = [ticket.student_id]
        if ticket.assignee_id and ticket.assignee_id != operator.id:
            notify_ids.append(ticket.assignee_id)
        cls._notify_ticket_event('ticket_processing', ticket, notify_ids)

        return ticket

    @classmethod
    @transaction.atomic
    def request_confirmation(cls, ticket: Ticket, operator: User, remark: str = '') -> Ticket:
        if ticket.status != Ticket.STATUS_PROCESSING:
            raise ValueError(f'当前状态 {ticket.get_status_display()} 不可请求确认')

        old_status = ticket.status
        ticket.status = Ticket.STATUS_WAITING_CONFIRM
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=['status', 'resolved_at', 'updated_at'])

        content = f'处理完成，请学生确认'
        if remark:
            content += f'。处理说明：{remark}'
        TicketReply.objects.create(
            ticket=ticket,
            author=operator,
            content=content,
            action_type='status_change',
            action_detail={'from_status': old_status, 'to_status': Ticket.STATUS_WAITING_CONFIRM},
        )

        notify_ids = [ticket.student_id]
        if ticket.assignee_id and ticket.assignee_id != operator.id:
            notify_ids.append(ticket.assignee_id)
        cls._notify_ticket_event('ticket_waiting_confirm', ticket, notify_ids, {
            'remark': remark or '',
        })

        return ticket

    @classmethod
    @transaction.atomic
    def student_confirm(cls, ticket: Ticket, student: User, is_confirmed: bool, reject_reason: str = '') -> Ticket:
        if ticket.status != Ticket.STATUS_WAITING_CONFIRM:
            raise ValueError(f'当前状态 {ticket.get_status_display()} 不可确认')
        if ticket.student_id != student.id:
            raise ValueError('只有提交工单的学生可确认')

        old_status = ticket.status
        if is_confirmed:
            ticket.status = Ticket.STATUS_COMPLETED
            ticket.save(update_fields=['status', 'updated_at'])
            TicketReply.objects.create(
                ticket=ticket,
                author=student,
                content='学生确认完成',
                action_type='status_change',
                action_detail={'from_status': old_status, 'to_status': Ticket.STATUS_COMPLETED},
            )
        else:
            ticket.status = Ticket.STATUS_PROCESSING
            ticket.save(update_fields=['status', 'updated_at'])
            content = '学生不认可处理结果'
            if reject_reason:
                content += f'，原因：{reject_reason}'
            TicketReply.objects.create(
                ticket=ticket,
                author=student,
                content=content,
                action_type='status_change',
                action_detail={'from_status': old_status, 'to_status': Ticket.STATUS_PROCESSING},
            )

        notify_ids = []
        if ticket.assignee_id:
            notify_ids.append(ticket.assignee_id)
        if notify_ids:
            cls._notify_ticket_event('ticket_confirmed', ticket, notify_ids, {
                'confirmed': '是' if is_confirmed else '否',
                'reject_reason': reject_reason or '',
            })

        return ticket

    @classmethod
    @transaction.atomic
    def rate_ticket(cls, ticket: Ticket, student: User, rating: int, comment: str = '') -> Ticket:
        if ticket.status != Ticket.STATUS_COMPLETED:
            raise ValueError(f'只有已完成的工单可评价，当前状态：{ticket.get_status_display()}')
        if ticket.student_id != student.id:
            raise ValueError('只有提交工单的学生可评价')
        if not 1 <= rating <= 5:
            raise ValueError('评分必须在 1-5 之间')

        ticket.rating = rating
        ticket.rating_comment = (comment or '').strip()
        ticket.rated_at = timezone.now()
        ticket.status = Ticket.STATUS_CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=['rating', 'rating_comment', 'rated_at', 'status', 'closed_at', 'updated_at'])

        TicketReply.objects.create(
            ticket=ticket,
            author=student,
            content=f'评价完成：{rating}星' + (f'，评价：{comment}' if comment else ''),
            action_type='rating',
            action_detail={'rating': rating, 'comment': comment or ''},
        )

        notify_ids = []
        if ticket.assignee_id:
            notify_ids.append(ticket.assignee_id)
        if notify_ids:
            cls._notify_ticket_event('ticket_rated', ticket, notify_ids, {
                'rating': str(rating),
                'comment': comment or '',
            })

        return ticket

    @classmethod
    @transaction.atomic
    def close_ticket(cls, ticket: Ticket, operator: User, reason: str = '') -> Ticket:
        if ticket.status == Ticket.STATUS_CLOSED:
            raise ValueError('工单已关闭')

        old_status = ticket.status
        ticket.status = Ticket.STATUS_CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=['status', 'closed_at', 'updated_at'])

        content = '工单已关闭'
        if reason:
            content += f'，原因：{reason}'
        TicketReply.objects.create(
            ticket=ticket,
            author=operator,
            content=content,
            action_type='status_change',
            action_detail={'from_status': old_status, 'to_status': Ticket.STATUS_CLOSED, 'reason': reason or ''},
        )

        notify_ids = [ticket.student_id]
        if ticket.assignee_id and ticket.assignee_id != operator.id:
            notify_ids.append(ticket.assignee_id)
        if notify_ids:
            cls._notify_ticket_event('ticket_closed', ticket, notify_ids, {'reason': reason or ''})

        return ticket

    @classmethod
    @transaction.atomic
    def add_reply(
        cls,
        ticket: Ticket,
        author: User,
        content: str,
        is_internal: bool = False,
        attachments: list[dict] | None = None,
    ) -> TicketReply:
        if ticket.status == Ticket.STATUS_CLOSED:
            raise ValueError('已关闭的工单不可回复')

        reply = TicketReply.objects.create(
            ticket=ticket,
            author=author,
            content=content.strip(),
            is_internal=is_internal,
            action_type='reply',
        )

        if attachments:
            for att in attachments:
                TicketAttachment.objects.create(
                    ticket=ticket,
                    reply=reply,
                    uploaded_by=author,
                    file_name=att.get('file_name', ''),
                    file_url=att.get('file_url', ''),
                    file_size=att.get('file_size', 0),
                    mime_type=att.get('mime_type', ''),
                )

        if not is_internal:
            notify_ids = []
            if author.id != ticket.student_id:
                notify_ids.append(ticket.student_id)
            if ticket.assignee_id and author.id != ticket.assignee_id:
                notify_ids.append(ticket.assignee_id)
            if notify_ids:
                cls._notify_ticket_event('ticket_reply', ticket, notify_ids, {
                    'reply_author': author.username,
                    'reply_content': content.strip()[:100],
                })

        return reply

    @classmethod
    def check_and_escalate_sla(cls, ticket: Ticket) -> bool:
        if ticket.status in (Ticket.STATUS_COMPLETED, Ticket.STATUS_CLOSED):
            return False
        if not ticket.is_sla_breached:
            return False

        cfg = cls._get_sla_config(ticket.priority)
        if cfg and not cfg.auto_escalate:
            return False

        now = timezone.now()
        last_log = ticket.escalation_logs.order_by('-created_at').first()
        escalation_interval = timedelta(hours=cfg.escalation_hours if cfg else 2)
        if last_log and (now - last_log.created_at) < escalation_interval:
            return False

        new_level = ticket.escalation_level + 1
        ticket.escalation_level = new_level
        ticket.save(update_fields=['escalation_level', 'updated_at'])

        TicketEscalationLog.objects.create(
            ticket=ticket,
            escalation_level=new_level,
            from_status=ticket.status,
            reason=f'SLA超时，已超过处理时限，自动升级至Lv.{new_level}',
        )

        admin_ids = list(
            User.objects.filter(profile__role='admin', is_active=True).values_list('id', flat=True)
        )
        if admin_ids:
            cls._notify_ticket_event('ticket_sla_breached', ticket, admin_ids, {
                'escalation_level': str(new_level),
            })

        logger.warning('Ticket #%s SLA breached, escalated to level %s', ticket.id, new_level)
        return True

    @classmethod
    def batch_check_sla(cls) -> int:
        open_tickets = Ticket.objects.filter(
            status__in=[
                Ticket.STATUS_PENDING,
                Ticket.STATUS_ASSIGNED,
                Ticket.STATUS_PROCESSING,
                Ticket.STATUS_WAITING_CONFIRM,
            ],
            sla_deadline__isnull=False,
            sla_deadline__lt=timezone.now(),
        ).select_related('student', 'assignee')

        count = 0
        for ticket in open_tickets:
            if cls.check_and_escalate_sla(ticket):
                count += 1
        return count

    @staticmethod
    def get_user_visible_tickets(user: User):
        role = getattr(user.profile, 'role', 'student')
        qs = Ticket.objects.select_related('student', 'assignee', 'room').prefetch_related('replies', 'attachments')
        if role == 'admin':
            return qs
        return qs.filter(
            Q(student=user) | Q(assignee=user)
        )

    @staticmethod
    def get_admin_users():
        return User.objects.filter(
            profile__role='admin',
            is_active=True,
        ).select_related('profile').order_by('username')
