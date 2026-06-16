from django.urls import path

from . import views

urlpatterns = [
    path("roles/", views.roles_view, name="roles"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("me/", views.me_view, name="me"),
    path("verify-otp/", views.verify_otp_view, name="verify-otp"),
    path("resend-otp/", views.resend_otp_view, name="resend-otp"),
    path(
        "password-reset/request/",
        views.password_reset_request_view,
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        views.password_reset_confirm_view,
        name="password-reset-confirm",
    ),
    path("profile/", views.profile_view, name="profile"),
    path("profile/avatar/", views.remove_avatar_view, name="remove-avatar"),
    path("become-sponsor/", views.become_sponsor_view, name="become-sponsor"),
    path(
        "superadmin/create-user/",
        views.superadmin_create_user_view,
        name="superadmin-create-user",
    ),
    # Hierarchical admin user creation (role-based)
    path(
        "union-admin/create-user/",
        views.union_admin_create_user_view,
        name="union-admin-create-user",
    ),
    path(
        "league-admin/create-user/",
        views.league_admin_create_user_view,
        name="league-admin-create-user",
    ),
    path(
        "club-admin/create-user/",
        views.club_admin_create_user_view,
        name="club-admin-create-user",
    ),
]
