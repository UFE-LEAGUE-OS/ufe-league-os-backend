from django.urls import path

from . import views

urlpatterns = [
    # Permissions
    path("permissions/", views.permission_list_view, name="permission-list"),
    path(
        "permissions/<int:pk>/", views.permission_detail_view, name="permission-detail"
    ),
    # Permission bundles
    path(
        "bundles/",
        views.permission_bundle_list_create_view,
        name="permission-bundle-list-create",
    ),
    path(
        "bundles/<int:pk>/",
        views.permission_bundle_detail_view,
        name="permission-bundle-detail",
    ),
    # Role templates
    path(
        "role-templates/",
        views.role_template_list_create_view,
        name="role-template-list-create",
    ),
    path(
        "role-templates/<int:pk>/",
        views.role_template_detail_view,
        name="role-template-detail",
    ),
    # User role assignments
    path(
        "assignments/",
        views.user_role_assignment_list_create_view,
        name="user-role-assignment-list-create",
    ),
    path(
        "assignments/<int:pk>/",
        views.user_role_assignment_detail_view,
        name="user-role-assignment-detail",
    ),
    # User permission overrides
    path(
        "overrides/",
        views.user_permission_override_list_create_view,
        name="user-permission-override-list-create",
    ),
    path(
        "overrides/<int:pk>/",
        views.user_permission_override_detail_view,
        name="user-permission-override-detail",
    ),
    # Sessions
    path("sessions/", views.session_list_view, name="session-list"),
    path("sessions/<int:pk>/", views.session_detail_view, name="session-detail"),
    # Impersonation
    path(
        "impersonation/",
        views.impersonation_list_create_view,
        name="impersonation-list-create",
    ),
    path(
        "impersonation/<int:pk>/stop/",
        views.impersonation_stop_view,
        name="impersonation-stop",
    ),
]
