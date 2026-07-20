from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import Club
from .models import Announcement, ClubDocument, ComplianceChecklist, CommunicationLog
from .permissions import IsClubAdminOrSuperAdmin, IsClubAdminOrSuperAdminReadOnly
from .serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    ClubDocumentCreateSerializer,
    ClubDocumentSerializer,
    ComplianceChecklistCreateSerializer,
    ComplianceChecklistSerializer,
    CommunicationLogSerializer,
)
from .services import (
    archive_document,
    mark_compliance_completed,
    publish_announcement,
    reopen_compliance_task,
    replace_document,
    unpublish_announcement,
)


class ClubDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsClubAdminOrSuperAdmin]
    queryset = ClubDocument.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ClubDocumentSerializer
        return ClubDocumentCreateSerializer

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not assigned as a club admin.")
        serializer.save(club=club)

    def get_queryset(self):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club and self.request.user.role != "SUPER_ADMIN":
            return ClubDocument.objects.none()
        queryset = super().get_queryset()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at"])

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        document = self.get_object()
        archive_document(document)
        return Response({"status": "archived"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def replace(self, request, pk=None):
        document = self.get_object()
        new_file = request.FILES.get("file")
        if not new_file:
            return Response(
                {"file": "This field is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        notes = request.data.get("notes")
        try:
            new_document = replace_document(
                document, new_file, request.user, notes=notes
            )
            serializer = ClubDocumentSerializer(
                new_document, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


class ComplianceChecklistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsClubAdminOrSuperAdmin]
    queryset = ComplianceChecklist.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ComplianceChecklistSerializer
        return ComplianceChecklistCreateSerializer

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not assigned as a club admin.")
        serializer.save(club=club)

    def get_queryset(self):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club and self.request.user.role != "SUPER_ADMIN":
            return ComplianceChecklist.objects.none()
        queryset = super().get_queryset()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at"])

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        item = self.get_object()
        try:
            mark_compliance_completed(item, request.user)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        item = self.get_object()
        try:
            reopen_compliance_task(item)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AnnouncementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsClubAdminOrSuperAdmin]
    queryset = Announcement.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return AnnouncementSerializer
        return AnnouncementCreateSerializer

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not assigned as a club admin.")
        serializer.save(club=club, created_by=self.request.user)

    def get_queryset(self):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club and self.request.user.role != "SUPER_ADMIN":
            return Announcement.objects.none()
        queryset = super().get_queryset()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at"])

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        announcement = self.get_object()
        try:
            publish_announcement(announcement)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(announcement)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        announcement = self.get_object()
        try:
            unpublish_announcement(announcement)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(announcement)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CommunicationLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CommunicationLogSerializer
    permission_classes = [IsClubAdminOrSuperAdminReadOnly]

    def get_queryset(self):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club and self.request.user.role != "SUPER_ADMIN":
            return CommunicationLog.objects.none()
        queryset = CommunicationLog.objects.all()
        if club:
            queryset = queryset.filter(club=club)
        return queryset
