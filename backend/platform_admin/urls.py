from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"approvals", views.ApprovalLogViewSet, basename="approval-log")
router.register(
    r"chargebacks", views.ChargebackRefundViewSet, basename="chargeback-refund"
)

urlpatterns = [
    path("", include(router.urls)),
]