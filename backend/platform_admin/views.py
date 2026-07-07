from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin

from .models import Announcement, Banner, FeatureFlag, SystemMessage
from .serializers import (
    AnnouncementSerializer,
    BannerSerializer,
    FeatureFlagSerializer,
    SystemMessageSerializer,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def announcement_list_create_view(request):
    if request.method == "GET":
        queryset = Announcement.objects.all().order_by("-created_at")
        serializer = AnnouncementSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = AnnouncementSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def feature_flag_list_create_view(request):
    if request.method == "GET":
        queryset = FeatureFlag.objects.all().order_by("name")
        serializer = FeatureFlagSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = FeatureFlagSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def banner_list_create_view(request):
    if request.method == "GET":
        queryset = Banner.objects.all().order_by("-created_at")
        serializer = BannerSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = BannerSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def system_message_list_create_view(request):
    if request.method == "GET":
        queryset = SystemMessage.objects.all().order_by("-created_at")
        serializer = SystemMessageSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = SystemMessageSerializer(
        data=request.data, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)
