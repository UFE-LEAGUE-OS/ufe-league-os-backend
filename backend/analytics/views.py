from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin

from .models import ReportAccessLog
from .serializers import ReportAccessLogSerializer


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def platform_summary_view(request):
    """Platform-wide summary analytics."""
    from accounts.models import User
    from memberships.models import Membership
    from ticketing.models import TicketOrder, Ticket
    from sponsorships.models import SponsorAccount, SponsorshipAgreement

    data = [
        {"metric": "Total Users", "value": User.objects.count(), "category": "users"},
        {
            "metric": "Active Users (30 days)",
            "value": User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=30)
            ).count(),
            "category": "users",
        },
        {
            "metric": "Verified Users",
            "value": User.objects.filter(is_email_verified=True).count(),
            "category": "users",
        },
        {
            "metric": "Active Memberships",
            "value": Membership.objects.filter(status=Membership.Status.ACTIVE).count(),
            "category": "memberships",
        },
        {
            "metric": "Expired Memberships",
            "value": Membership.objects.filter(
                status=Membership.Status.EXPIRED
            ).count(),
            "category": "memberships",
        },
        {
            "metric": "Pending Ticket Orders",
            "value": TicketOrder.objects.filter(
                status=TicketOrder.Status.PENDING
            ).count(),
            "category": "ticketing",
        },
        {
            "metric": "Paid Ticket Orders",
            "value": TicketOrder.objects.filter(status=TicketOrder.Status.PAID).count(),
            "category": "ticketing",
        },
        {
            "metric": "Tickets Issued",
            "value": Ticket.objects.count(),
            "category": "ticketing",
        },
        {
            "metric": "Active Sponsor Accounts",
            "value": SponsorAccount.objects.filter(is_active=True).count(),
            "category": "sponsorships",
        },
        {
            "metric": "Active Sponsorship Agreements",
            "value": SponsorshipAgreement.objects.filter(
                status=SponsorshipAgreement.Status.ACTIVE
            ).count(),
            "category": "sponsorships",
        },
    ]

    return Response(
        {
            "data": data,
            "generated_at": timezone.now(),
            "total_records": len(data),
        }
    )


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

    if period == "daily":
        users = users.extra(select={"period": "DATE_TRUNC('day', date_joined)"})
    elif period == "weekly":
        users = users.extra(select={"period": "DATE_TRUNC('week', date_joined)"})
    else:
        users = users.extra(select={"period": "DATE_TRUNC('month', date_joined)"})

    growth_data = [{"period": "aggregated", "count": users.count()}]

    return Response(
        {
            "data": growth_data,
            "filters": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "period": period,
            },
            "generated_at": timezone.now(),
            "total_records": len(growth_data),
        }
    )


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def engagement_analytics_view(request):
    """Engagement analytics."""
    from engagements.models import Follow, Event, Poll, Prediction

    data = [
        {
            "metric": "Total Follows",
            "value": Follow.objects.count(),
            "category": "engagement",
        },
        {
            "metric": "Total Events",
            "value": Event.objects.count(),
            "category": "engagement",
        },
        {
            "metric": "Total Polls",
            "value": Poll.objects.count(),
            "category": "engagement",
        },
        {
            "metric": "Total Predictions",
            "value": Prediction.objects.count(),
            "category": "engagement",
        },
    ]

    return Response(
        {
            "data": data,
            "generated_at": timezone.now(),
            "total_records": len(data),
        }
    )


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def membership_analytics_view(request):
    """Membership analytics."""
    from memberships.models import Membership

    data = [
        {
            "metric": "Active Memberships",
            "value": Membership.objects.filter(status=Membership.Status.ACTIVE).count(),
            "category": "memberships",
        },
        {
            "metric": "Expired Memberships",
            "value": Membership.objects.filter(
                status=Membership.Status.EXPIRED
            ).count(),
            "category": "memberships",
        },
        {
            "metric": "Suspended Memberships",
            "value": Membership.objects.filter(
                status=Membership.Status.SUSPENDED
            ).count(),
            "category": "memberships",
        },
    ]

    return Response(
        {
            "data": data,
            "generated_at": timezone.now(),
            "total_records": len(data),
        }
    )


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def ticketing_analytics_view(request):
    """Ticketing analytics."""
    from ticketing.models import TicketOrder, Ticket

    data = [
        {
            "metric": "Pending Orders",
            "value": TicketOrder.objects.filter(
                status=TicketOrder.Status.PENDING
            ).count(),
            "category": "ticketing",
        },
        {
            "metric": "Paid Orders",
            "value": TicketOrder.objects.filter(status=TicketOrder.Status.PAID).count(),
            "category": "ticketing",
        },
        {
            "metric": "Cancelled Orders",
            "value": TicketOrder.objects.filter(
                status=TicketOrder.Status.CANCELLED
            ).count(),
            "category": "ticketing",
        },
        {
            "metric": "Tickets Issued",
            "value": Ticket.objects.count(),
            "category": "ticketing",
        },
    ]

    return Response(
        {
            "data": data,
            "generated_at": timezone.now(),
            "total_records": len(data),
        }
    )


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def sponsorship_analytics_view(request):
    """Sponsorship analytics."""
    from sponsorships.models import SponsorAccount, SponsorshipAgreement

    data = [
        {
            "metric": "Active Sponsor Accounts",
            "value": SponsorAccount.objects.filter(is_active=True).count(),
            "category": "sponsorships",
        },
        {
            "metric": "Active Agreements",
            "value": SponsorshipAgreement.objects.filter(
                status=SponsorshipAgreement.Status.ACTIVE
            ).count(),
            "category": "sponsorships",
        },
        {
            "metric": "Total Agreements",
            "value": SponsorshipAgreement.objects.count(),
            "category": "sponsorships",
        },
    ]

    return Response(
        {
            "data": data,
            "generated_at": timezone.now(),
            "total_records": len(data),
        }
    )


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

    data = [
        {"metric": "Database Status", "value": db_status, "category": "system"},
        {"metric": "Total Users", "value": User.objects.count(), "category": "system"},
        {
            "metric": "Open Anomalies",
            "value": Anomaly.objects.filter(status=Anomaly.Status.OPEN).count(),
            "category": "system",
        },
        {
            "metric": "Unresolved Security Events",
            "value": SecurityEvent.objects.filter(is_resolved=False).count(),
            "category": "system",
        },
    ]

    return Response(
        {
            "data": data,
            "generated_at": timezone.now(),
            "total_records": len(data),
        }
    )


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
    return Response(
        {
            "data": serializer.data,
            "total_records": queryset.count(),
        }
    )
