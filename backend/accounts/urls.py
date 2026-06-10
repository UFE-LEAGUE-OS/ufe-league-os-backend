from django.urls import path

from . import views


urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("me/", views.me_view, name="me"),
    path("verify-otp/", views.verify_otp_view, name="verify-otp"),
    path("resend-otp/", views.resend_otp_view, name="resend-otp"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/avatar/", views.remove_avatar_view, name="remove-avatar"),
]
