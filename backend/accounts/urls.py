from django.urls import path

from . import views
from . import views_extra

urlpatterns = [
    path("config/", views.config_view, name="config"),
    path("roles/", views.roles_view, name="roles"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("google/", views.google_auth_view, name="google-auth"),
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
    # Follow / Unfollow
    path("follow/", views_extra.follow_view, name="follow"),
    path(
        "follow/check/<str:content_type>/<int:object_id>/",
        views_extra.check_follow_view,
        name="follow-check",
    ),
    # Notification preferences
    path(
        "notification-preferences/me/",
        views_extra.notification_preferences_me_view,
        name="notification-preferences-me",
    ),
    path(
        "notifications/",
        views_extra.notification_preferences_view,
        name="notification-preferences",
    ),
    # Interest & privacy preferences
    path(
        "interests/",
        views_extra.interest_preferences_view,
        name="interest-preferences",
    ),
    # Wallet
    path("wallet/", views_extra.wallet_view, name="wallet"),
    # Payment history
    path("payments/", views_extra.payment_history_view, name="payment-history"),
    # Switch workspace / account
    path(
        "switch-workspace/",
        views.switch_workspace_view,
        name="switch-workspace",
    ),
    # Role approval workflow
    path(
        "role-approvals/",
        views.role_approval_list_view,
        name="role-approval-list",
    ),
    path(
        "role-approvals/pending-count/",
        views.role_approval_pending_count_view,
        name="role-approval-pending-count",
    ),
    path(
        "role-approvals/<int:pk>/review/",
        views.role_approval_review_view,
        name="role-approval-review",
    ),
    # Personalized feed
    path("feed/", views_extra.feed_view, name="feed"),
    path(
        "feed/mark-read/<int:feed_item_id>/",
        views_extra.feed_mark_read_view,
        name="feed-mark-read",
    ),
    path(
        "feed/mark-all-read/",
        views_extra.feed_mark_all_read_view,
        name="feed-mark-all-read",
    ),
    path(
        "feed/unread-count/",
        views_extra.feed_unread_count_view,
        name="feed-unread-count",
    ),
]
