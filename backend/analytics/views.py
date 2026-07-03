from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin

from .models import ReportAccessLog
from .serializers import (
    ReportAccessLogSerializer,
)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def platform_summary_view(request):
    """Platform-wide summary analytics."""
    from accounts.models import User
    from memberships.models import Membership
    from ticketing.models import TicketOrder, Ticket
    from sponsorships.models import SponsorAccount, SponsorshipAgreement

    summary = {
        "users": {
            "total": User.objects.count(),
            "active_last_30_days": User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=30)
            ).count(),
            "verified": User.objects.filter(is_email_verified=True).count(),
        },
        "memberships": {
            "total_active": Membership.objects.filter(
                status=Membership.Status.ACTIVE
            ).count(),
            "total_expired": Membership.objects.filter(
                status=Membership.Status.EXPIRED
            ).count(),
        },
        "ticketing": {
            "orders_pending": TicketOrder.objects.filter(
                status=TicketOrder.Status.PENDING
            ).count(),
            "orders_paid": TicketOrder.objects.filter(
                status=TicketOrder.Status.PAID
            ).count(),
            "tickets_issued": Ticket.objects.count(),
        },
        "sponsorships": {
            "active_accounts": SponsorAccount.objects.filter(is_active=True).count(),
            "active_agreements": SponsorshipAgreement.objects.filter(
                status=SponsorshipAgreement.Status.ACTIVE
            ).count(),
        },
        "generated_at": timezone.now(),
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.PLATFORM_SUMMARY,
        action=ReportAccessLog.ActionType.VIEW,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(summary)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def user_growth_view(request):
    """User growth analytics with optional date filtering."""
    from accounts.models import User
    from datetime import datetime

    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")
    period = request.query_params.get("period", "monthly")

    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start_date = timezone.now().date() - timedelta(days=365)

    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end_date = timezone.now().date()

    users = User.objects.filter(date_joined__date__range=[start_date, end_date])
    total = users.count()

    growth_data = {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "total_users": total,
        "new_users": total,
        "data": [],
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.USER_GROWTH,
        action=ReportAccessLog.ActionType.VIEW,
        filters_applied={
            "start_date": str(start_date),
            "end_date": str(end_date),
            "period": period,
        },
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(growth_data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def engagement_analytics_view(request):
    """Engagement analytics."""
    from engagements.models import Follow, Event, Poll, Prediction

    data = {
        "total_follows": Follow.objects.count(),
        "total_events": Event.objects.count(),
        "total_polls": Poll.objects.count(),
        "total_predictions": Prediction.objects.count(),
        "generated_at": timezone.now(),
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.ENGAGEMENT,
        action=ReportAccessLog.ActionType.VIEW,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def membership_analytics_view(request):
    """Membership analytics."""
    from memberships.models import Membership

    active = Membership.objects.filter(status=Membership.Status.ACTIVE).count()
    expired = Membership.objects.filter(status=Membership.Status.EXPIRED).count()
    suspended = Membership.objects.filter(status=Membership.Status.SUSPENDED).count()

    data = {
        "active": active,
        "expired": expired,
        "suspended": suspended,
        "total": active + expired + suspended,
        "generated_at": timezone.now(),
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.MEMBERSHIP,
        action=ReportAccessLog.ActionType.VIEW,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def ticketing_analytics_view(request):
    """Ticketing analytics."""
    from ticketing.models import TicketOrder, Ticket

    pending = TicketOrder.objects.filter(status=TicketOrder.Status.PENDING).count()
    paid = TicketOrder.objects.filter(status=TicketOrder.Status.PAID).count()
    cancelled = TicketOrder.objects.filter(status=TicketOrder.Status.CANCELLED).count()
    total_tickets = Ticket.objects.count()

    data = {
        "orders_pending": pending,
        "orders_paid": paid,
        "orders_cancelled": cancelled,
        "total_orders": pending + paid + cancelled,
        "total_tickets": total_tickets,
        "generated_at": timezone.now(),
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.TICKETING,
        action=ReportAccessLog.ActionType.VIEW,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def sponsorship_analytics_view(request):
    """Sponsorship analytics."""
    from sponsorships.models import SponsorAccount, SponsorshipAgreement

    active_accounts = SponsorAccount.objects.filter(is_active=True).count()
    active_agreements = SponsorshipAgreement.objects.filter(
        status=SponsorshipAgreement.Status.ACTIVE
    ).count()
    total_agreements = SponsorshipAgreement.objects.count()

    data = {
        "active_accounts": active_accounts,
        "active_agreements": active_agreements,
        "total_agreements": total_agreements,
        "generated_at": timezone.now(),
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.SPONSORSHIP,
        action=ReportAccessLog.ActionType.VIEW,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def system_health_view(request):
    """System health metrics."""
    from django.db import connection
    from accounts.models import User
    from monitoring.models import Anomaly, SecurityEvent

    try:
        connection.ensure_connection()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    open_anomalies = Anomaly.objects.filter(status=Anomaly.Status.OPEN).count()
    unresolved_security_events = SecurityEvent.objects.filter(is_resolved=False).count()

    data = {
        "database_status": db_status,
        "total_users": User.objects.count(),
        "open_anomalies": open_anomalies,
        "unresolved_security_events": unresolved_security_events,
        "generated_at": timezone.now(),
    }

    ReportAccessLog.objects.create(
        user=request.user,
        report_type=ReportAccessLog.ReportType.SYSTEM_HEALTH,
        action=ReportAccessLog.ActionType.VIEW,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def analytics_report_access_log_view(request):
    """List analytics report access logs with optional filters."""
    queryset = ReportAccessLog.objects.all().order_by("-created_at")

    report_type = request.query_params.get("report_type")
    if report_type:
        queryset = queryset.filter(report_type=report_type)

    action = request.query_params.get("action")
    if action:
        queryset = queryset.filter(action=action)

    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    serializer = ReportAccessLogSerializer(queryset, many=True)
    return Response(serializer.data)
