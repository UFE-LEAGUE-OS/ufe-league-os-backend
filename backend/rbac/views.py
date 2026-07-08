from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin
from accounts.rbac import log_governance_action

from .models import (
    RoleTemplate,
    PermissionBundle,
    Permission,
    UserRoleAssignment,
    UserPermissionOverride,
    Session,
    ImpersonationLog,
)
from .serializers import (
    PermissionSerializer,
    PermissionBundleSerializer,
    RoleTemplateSerializer,
    UserRoleAssignmentSerializer,
    UserPermissionOverrideSerializer,
    SessionSerializer,
    ImpersonationLogSerializer,
)

# ---------------------------------------------------------------------------
# PERMISSIONS
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def permission_list_view(request):
    """List all permissions with optional filters."""
    queryset = Permission.objects.all().order_by("category", "codename")
    category = request.query_params.get("category")
    if category:
        queryset = queryset.filter(category=category)
    bundle_id = request.query_params.get("bundle_id")
    if bundle_id:
        queryset = queryset.filter(bundle_id=bundle_id)
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(codename__icontains=search)
    serializer = PermissionSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def permission_detail_view(request, pk):
    """Retrieve a single permission."""
    try:
        permission = Permission.objects.get(pk=pk)
    except Permission.DoesNotExist:
        return Response(
            {"detail": "Permission not found."}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = PermissionSerializer(permission)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# PERMISSION BUNDLES
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def permission_bundle_list_create_view(request):
    """List or create permission bundles."""
    if request.method == "GET":
        queryset = PermissionBundle.objects.all().order_by("name")
        serializer = PermissionBundleSerializer(queryset, many=True)
        return Response(serializer.data)
    serializer = PermissionBundleSerializer(data=request.data)
    if serializer.is_valid():
        bundle = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_permission_bundle",
            details={"bundle_id": bundle.id, "name": bundle.name},
        )
        return Response(
            PermissionBundleSerializer(bundle).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def permission_bundle_detail_view(request, pk):
    """Retrieve, update, or delete a permission bundle."""
    try:
        bundle = PermissionBundle.objects.get(pk=pk)
    except PermissionBundle.DoesNotExist:
        return Response(
            {"detail": "Permission bundle not found."}, status=status.HTTP_404_NOT_FOUND
        )
    if request.method == "GET":
        serializer = PermissionBundleSerializer(bundle)
        return Response(serializer.data)
    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = PermissionBundleSerializer(
            bundle, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            log_governance_action(
                actor=request.user,
                action="update_permission_bundle",
                details={"bundle_id": bundle.id},
            )
            return Response(PermissionBundleSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    bundle.delete()
    log_governance_action(
        actor=request.user,
        action="delete_permission_bundle",
        details={"bundle_id": bundle.id},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# ROLE TEMPLATES
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def role_template_list_create_view(request):
    """List or create role templates."""
    if request.method == "GET":
        queryset = RoleTemplate.objects.all().order_by("name")
        serializer = RoleTemplateSerializer(queryset, many=True)
        return Response(serializer.data)
    serializer = RoleTemplateSerializer(data=request.data)
    if serializer.is_valid():
        role_template = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_role_template",
            details={"role_template_id": role_template.id, "name": role_template.name},
        )
        return Response(
            RoleTemplateSerializer(role_template).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def role_template_detail_view(request, pk):
    """Retrieve, update, or delete a role template."""
    try:
        role_template = RoleTemplate.objects.get(pk=pk)
    except RoleTemplate.DoesNotExist:
        return Response(
            {"detail": "Role template not found."}, status=status.HTTP_404_NOT_FOUND
        )
    if request.method == "GET":
        serializer = RoleTemplateSerializer(role_template)
        return Response(serializer.data)
    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = RoleTemplateSerializer(
            role_template, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            log_governance_action(
                actor=request.user,
                action="update_role_template",
                details={"role_template_id": role_template.id},
            )
            return Response(RoleTemplateSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    role_template.delete()
    log_governance_action(
        actor=request.user,
        action="delete_role_template",
        details={"role_template_id": role_template.id},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# USER ROLE ASSIGNMENTS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def user_role_assignment_list_create_view(request):
    """List or create user role assignments."""
    if request.method == "GET":
        queryset = UserRoleAssignment.objects.all().order_by("-created_at")
        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        role_template_id = request.query_params.get("role_template_id")
        if role_template_id:
            queryset = queryset.filter(role_template_id=role_template_id)
        serializer = UserRoleAssignmentSerializer(queryset, many=True)
        return Response(serializer.data)
    serializer = UserRoleAssignmentSerializer(data=request.data)
    if serializer.is_valid():
        assignment = serializer.save()
        log_governance_action(
            actor=request.user,
            action="assign_role_template",
            details={
                "assignment_id": assignment.id,
                "user_id": assignment.user_id,
                "role_template_id": assignment.role_template_id,
            },
        )
        return Response(
            UserRoleAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def user_role_assignment_detail_view(request, pk):
    """Retrieve, update, or delete a user role assignment."""
    try:
        assignment = UserRoleAssignment.objects.get(pk=pk)
    except UserRoleAssignment.DoesNotExist:
        return Response(
            {"detail": "User role assignment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        serializer = UserRoleAssignmentSerializer(assignment)
        return Response(serializer.data)
    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = UserRoleAssignmentSerializer(
            assignment, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            log_governance_action(
                actor=request.user,
                action="update_user_role_assignment",
                details={"assignment_id": assignment.id},
            )
            return Response(UserRoleAssignmentSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    assignment.delete()
    log_governance_action(
        actor=request.user,
        action="delete_user_role_assignment",
        details={"assignment_id": assignment.id},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# USER PERMISSION OVERRIDES
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def user_permission_override_list_create_view(request):
    """List or create user permission overrides."""
    if request.method == "GET":
        queryset = UserPermissionOverride.objects.all().order_by("-created_at")
        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        permission_id = request.query_params.get("permission_id")
        if permission_id:
            queryset = queryset.filter(permission_id=permission_id)
        effect = request.query_params.get("effect")
        if effect:
            queryset = queryset.filter(effect=effect)
        serializer = UserPermissionOverrideSerializer(queryset, many=True)
        return Response(serializer.data)
    serializer = UserPermissionOverrideSerializer(data=request.data)
    if serializer.is_valid():
        override = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_permission_override",
            details={
                "override_id": override.id,
                "user_id": override.user_id,
                "permission_id": override.permission_id,
                "effect": override.effect,
            },
        )
        return Response(
            UserPermissionOverrideSerializer(override).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def user_permission_override_detail_view(request, pk):
    """Retrieve, update, or delete a user permission override."""
    try:
        override = UserPermissionOverride.objects.get(pk=pk)
    except UserPermissionOverride.DoesNotExist:
        return Response(
            {"detail": "Permission override not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        serializer = UserPermissionOverrideSerializer(override)
        return Response(serializer.data)
    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = UserPermissionOverrideSerializer(
            override, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            log_governance_action(
                actor=request.user,
                action="update_permission_override",
                details={"override_id": override.id},
            )
            return Response(UserPermissionOverrideSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    override.delete()
    log_governance_action(
        actor=request.user,
        action="delete_permission_override",
        details={"override_id": override.id},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# SESSIONS
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def session_list_view(request):
    """List active sessions with optional filters."""
    queryset = Session.objects.all().order_by("-last_accessed")
    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    is_active = request.query_params.get("is_active")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active.lower() == "true")
    serializer = SessionSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def session_detail_view(request, pk):
    """Retrieve or revoke a session."""
    try:
        session = Session.objects.get(pk=pk)
    except Session.DoesNotExist:
        return Response(
            {"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND
        )
    if request.method == "GET":
        serializer = SessionSerializer(session)
        return Response(serializer.data)
    session.is_active = False
    session.save(update_fields=["is_active"])
    log_governance_action(
        actor=request.user,
        action="revoke_session",
        details={"session_id": session.id, "user_id": session.user_id},
    )
    return Response(
        {"detail": "Session revoked.", "session": SessionSerializer(session).data}
    )


# ---------------------------------------------------------------------------
# IMPERSONATION
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def impersonation_list_create_view(request):
    """List or start impersonation sessions."""
    if request.method == "GET":
        queryset = ImpersonationLog.objects.all().order_by("-started_at")
        admin_id = request.query_params.get("admin_id")
        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)
        target_user_id = request.query_params.get("target_user_id")
        if target_user_id:
            queryset = queryset.filter(target_user_id=target_user_id)
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        serializer = ImpersonationLogSerializer(queryset, many=True)
        return Response(serializer.data)
    target_user_id = request.data.get("target_user_id")
    reason = request.data.get("reason", "")
    if not target_user_id:
        return Response(
            {"detail": "target_user_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        target_user = User.objects.get(pk=target_user_id)
    except User.DoesNotExist:
        return Response(
            {"detail": "Target user not found."}, status=status.HTTP_404_NOT_FOUND
        )
    existing = ImpersonationLog.objects.filter(
        admin=request.user, is_active=True
    ).first()
    if existing:
        return Response(
            {"detail": "You already have an active impersonation session."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    impersonation = ImpersonationLog.objects.create(
        admin=request.user,
        target_user=target_user,
        reason=reason,
        ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    log_governance_action(
        actor=request.user,
        action="start_impersonation",
        details={
            "impersonation_id": impersonation.id,
            "target_user_id": target_user.id,
        },
    )
    return Response(
        ImpersonationLogSerializer(impersonation).data, status=status.HTTP_201_CREATED
    )


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def impersonation_stop_view(request, pk):
    """Stop an active impersonation session."""
    try:
        impersonation = ImpersonationLog.objects.get(pk=pk)
    except ImpersonationLog.DoesNotExist:
        return Response(
            {"detail": "Impersonation log not found."}, status=status.HTTP_404_NOT_FOUND
        )
    if not impersonation.is_active:
        return Response(
            {"detail": "Impersonation session is not active."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if impersonation.admin != request.user:
        return Response(
            {"detail": "You cannot stop another admin's impersonation session."},
            status=status.HTTP_403_FORBIDDEN,
        )
    impersonation.is_active = False
    impersonation.ended_at = timezone.now()
    impersonation.save(update_fields=["is_active", "ended_at"])
    log_governance_action(
        actor=request.user,
        action="stop_impersonation",
        details={"impersonation_id": impersonation.id},
    )
    return Response(
        {
            "detail": "Impersonation stopped.",
            "impersonation": ImpersonationLogSerializer(impersonation).data,
        }
    )
