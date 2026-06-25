from django.urls import path

from . import views

urlpatterns = [
    path(
        "matches/<int:match_id>/ticket-types/",
        views.match_ticket_types_view,
        name="ticketing-match-ticket-types",
    ),
    path(
        "orders/",
        views.my_ticket_orders_view,
        name="ticketing-orders",
    ),
    path(
        "orders/flutterwave/initialize/",
        views.ticket_order_flutterwave_initialize_view,
        name="ticketing-flutterwave-initialize",
    ),
    path(
        "tickets/me/",
        views.my_tickets_view,
        name="ticketing-my-tickets",
    ),
    path(
        "flutterwave/verify/",
        views.ticket_flutterwave_verify_view,
        name="ticketing-flutterwave-verify",
    ),
    path(
        "flutterwave/webhook/",
        views.ticket_flutterwave_webhook_view,
        name="ticketing-flutterwave-webhook",
    ),
    path(
        "validate/",
        views.ticket_validate_view,
        name="ticketing-validate",
    ),
    path(
        "reservations/expire/",
        views.expire_ticket_reservations_view,
        name="ticketing-expire-reservations",
    ),
    path(
        "tickets/<int:ticket_id>/qr/",
        views.ticket_qr_svg_view,
        name="ticketing-ticket-qr-svg",
    ),
]
