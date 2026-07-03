from rest_framework import serializers

from .models import (
    RoleTemplate,
    PermissionBundle,
    Permission,
    RoleTemplatePermission,
    UserRoleAssignment,
    UserPermissionOverride,
    Session,
    ImpersonationLog,
)


class PermissionSerializer(serializers.ModelSerializer):
    bundle_name = serializers.CharField(source="bundle.name", read_only=True)
    bundle_slug = serializers.CharField(source="bundle.slug", read_only=True)

    class Meta:
        model = Permission
        fields = [
            "id",
            "bundle",
            "bundle_name",
            "bundle_slug",
            "codename",
            "name",
            "description",
            "category",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PermissionBundleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionBundle
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_system",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoleTemplatePermissionSerializer(serializers.ModelSerializer):
    permission_name = serializers.CharField(source="permission.name", read_only=True)
    permission_codename = serializers.CharField(
        source="permission.codename", read_only=True
    )

    class Meta:
        model = RoleTemplatePermission
        fields = [
            "id",
            "role_template",
            "permission",
            "permission_name",
            "permission_codename",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class RoleTemplateSerializer(serializers.ModelSerializer):
    permissions = RoleTemplatePermissionSerializer(
        source="template_permissions", many=True, read_only=True
    )
    permission_ids = serializers.ListField(write_only=True, required=False)

    class Meta:
        model = RoleTemplate
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_system",
            "is_active",
            "permissions",
            "permission_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        permission_ids = validated_data.pop("permission_ids", [])
        role_template = RoleTemplate.objects.create(**validated_data)
        self._set_permissions(role_template, permission_ids)
        return role_template

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop("permission_ids", [])
        instance.name = validated_data.get("name", instance.name)
        instance.slug = validated_data.get("slug", instance.slug)
        instance.description = validated_data.get("description", instance.description)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save(
            update_fields=["name", "slug", "description", "is_active", "updated_at"]
        )
        if permission_ids:
            self._set_permissions(instance, permission_ids)
        return instance

    def _set_permissions(self, role_template, permission_ids):
        from .models import RoleTemplatePermission

        RoleTemplatePermission.objects.filter(role_template=role_template).delete()
        for permission_id in permission_ids:
            RoleTemplatePermission.objects.create(
                role_template=role_template, permission_id=permission_id
            )


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    role_template_name = serializers.CharField(
        source="role_template.name", read_only=True
    )
    assigned_by_email = serializers.CharField(
        source="assigned_by.email", read_only=True
    )

    class Meta:
        model = UserRoleAssignment
        fields = [
            "id",
            "user",
            "user_email",
            "role_template",
            "role_template_name",
            "assigned_by",
            "assigned_by_email",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserPermissionOverrideSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    permission_codename = serializers.CharField(
        source="permission.codename", read_only=True
    )

    class Meta:
        model = UserPermissionOverride
        fields = [
            "id",
            "user",
            "user_email",
            "permission",
            "permission_codename",
            "effect",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SessionSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Session
        fields = [
            "id",
            "user",
            "user_email",
            "session_key",
            "ip_address",
            "user_agent",
            "is_active",
            "last_accessed",
            "created_at",
            "expires_at",
        ]
        read_only_fields = ["id", "created_at", "last_accessed"]


class ImpersonationLogSerializer(serializers.ModelSerializer):
    admin_email = serializers.CharField(source="admin.email", read_only=True)
    target_user_email = serializers.CharField(
        source="target_user.email", read_only=True
    )

    class Meta:
        model = ImpersonationLog
        fields = [
            "id",
            "admin",
            "admin_email",
            "target_user",
            "target_user_email",
            "reason",
            "started_at",
            "ended_at",
            "is_active",
            "ip_address",
            "user_agent",
        ]
        read_only_fields = ["id", "started_at"]
