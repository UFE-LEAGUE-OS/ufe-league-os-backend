from django.urls import path

from . import views


urlpatterns = [
    path("register/", views.sponsor_register_view, name="sponsor-register"),
    path("accounts/", views.sponsor_accounts_view, name="sponsor-accounts"),
    path(
        "accounts/<int:account_id>/",
        views.sponsor_account_detail_view,
        name="sponsor-account-detail",
    ),
    path(
        "accounts/<int:account_id>/members/",
        views.sponsor_account_members_view,
        name="sponsor-account-members",
    ),
]
