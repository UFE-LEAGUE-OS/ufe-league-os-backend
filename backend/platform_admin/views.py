from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin
from .models import (
    Announcement,
    Banner,
    FeatureFlag,
    SystemMessage,
)
from .serializers import (
    AnnouncementSerializer,
    BannerSerializer,
    FeatureFlagSerializer,
    SystemMessageSerializer,
)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_platform_content_view(request):
    announcements = Announcement.objects.filter(is_active=True).order_by("-created_at")[
        :10
    ]
    banners = Banner.objects.filter(is_active=True).order_by("-created_at")[:5]
    system_messages = SystemMessage.objects.filter(is_active=True).order_by(
        "-created_at"
    )[:10]

    return Response(
        {
            "announcements": AnnouncementSerializer(announcements, many=True).data,
            "banners": BannerSerializer(banners, many=True).data,
            "system_messages": SystemMessageSerializer(system_messages, many=True).data,
            # The following have been removed as they are likely not intended for a generic public view.
            # - public_content (better fetched via its own slug-based endpoint)
            # - help_center_articles (better fetched via its own endpoint with search/category filters)
            # - broadcasts (audience-specific, may not be for 'public')
            # - feature_flags (internal configuration)
            # - notification_templates (internal configuration)
        }
    )


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform announcements.
    """

    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform feature flags.
    """

    queryset = FeatureFlag.objects.all().order_by("name")
    serializer_class = FeatureFlagSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BannerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform banners.
    """

    queryset = Banner.objects.all().order_by("-created_at")
    serializer_class = BannerSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SystemMessageViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform system messages.
    """

    queryset = SystemMessage.objects.all().order_by("-created_at")
    serializer_class = SystemMessageSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PublicContentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing public content pages and sections.
    """

    queryset = PublicContent.objects.all().order_by("title")
    serializer_class = PublicContentSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class HelpCenterArticleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing help center articles.
    """

    queryset = HelpCenterArticle.objects.all().order_by("title")
    serializer_class = HelpCenterArticleSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BroadcastViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing broadcasts.
    """

    queryset = Broadcast.objects.all().order_by("-created_at")
    serializer_class = BroadcastSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing notification templates.
    """

    queryset = NotificationTemplate.objects.all().order_by("name")
    serializer_class = NotificationTemplateSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
