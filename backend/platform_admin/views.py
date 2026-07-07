from rest_framework import viewsets

from accounts.permissions import IsSuperAdmin
from .models import Announcement, Banner, FeatureFlag, SystemMessage
from .serializers import (
    AnnouncementSerializer,
    BannerSerializer,
    FeatureFlagSerializer,
    SystemMessageSerializer,
)


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform announcements.
    """

    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer
    permission_classes = [IsSuperAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform feature flags.
    """

    queryset = FeatureFlag.objects.all().order_by("name")
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsSuperAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BannerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform banners.
    """

    queryset = Banner.objects.all().order_by("-created_at")
    serializer_class = BannerSerializer
    permission_classes = [IsSuperAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SystemMessageViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform system messages.
    """

    queryset = SystemMessage.objects.all().order_by("-created_at")
    serializer_class = SystemMessageSerializer
    permission_classes = [IsSuperAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
