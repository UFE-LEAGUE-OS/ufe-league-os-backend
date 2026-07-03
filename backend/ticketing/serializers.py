from rest_framework import serializers

from .models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketType,
    TicketValidationLog,
)
from .services.orders import validate_ticket_type_can_be_purchased


class TicketTypeSerializer(serializers.ModelSerializer):
    remaining_quantity = serializers.IntegerField(read_only=True)
    active_reserved_quantity = serializers.IntegerField(read_only=True)
    match_label = serializers.SerializerMethodField()

    class Meta:
        model = TicketType
        fields = [
            "id",
            "match",
            "match_label",
            "name",
            "description",
            "price",
            "currency",
            "quantity_available",
            "quantity_sold",
            "active_reserved_quantity",
            "remaining_quantity",
            "sale_start_at",
            "sale_end_at",
            "status",
        ]
        read_only_fields = [
            "id",
            "match_label",
            "quantity_sold",
            "active_reserved_quantity",
            "remaining_quantity",
        ]

    def get_qr_image_url(self, obj):
        request = self.context.get("request")
        path = f"/api/ticketing/tickets/{obj.id}/qr/"

        if request:
            return request.build_absolute_uri(path)

        return path

    def get_match_label(self, obj):
        return str(obj.match)


class TicketOrderItemSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    match_id = serializers.IntegerField(source="ticket_type.match_id", read_only=True)
    match_label = serializers.SerializerMethodField()

    class Meta:
        model = TicketOrderItem
        fields = [
            "id",
            "ticket_type",
            "ticket_type_name",
            "match_id",
            "match_label",
            "quantity",
            "unit_price",
            "total_price",
            "created_at",
        ]
        read_only_fields = fields

    def get_match_label(self, obj):
        return str(obj.ticket_type.match)


class TicketOrderSerializer(serializers.ModelSerializer):
    items = TicketOrderItemSerializer(many=True, read_only=True)
    tickets_count = serializers.SerializerMethodField()
    is_reservation_active = serializers.BooleanField(read_only=True)
    is_reservation_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketOrder
        fields = [
            "id",
            "buyer",
            "total_amount",
            "currency",
            "status",
            "provider",
            "payment_reference",
            "provider_transaction_id",
            "provider_status",
            "checkout_url",
            "checkout_initialized_at",
            "reservation_expires_at",
            "reservation_released_at",
            "is_reservation_active",
            "is_reservation_expired",
            "paid_at",
            "created_at",
            "updated_at",
            "items",
            "tickets_count",
        ]
        read_only_fields = fields

    def get_tickets_count(self, obj):
        return obj.tickets.count()


class FlutterwaveTicketCheckoutSerializer(serializers.Serializer):
    ticket_type_id = serializers.PrimaryKeyRelatedField(
        queryset=TicketType.objects.select_related(
            "match",
            "match__home_club",
            "match__away_club",
        ),
        source="ticket_type",
    )
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        ticket_type = attrs["ticket_type"]
        quantity = attrs["quantity"]
        validate_ticket_type_can_be_purchased(ticket_type, quantity)
        return attrs


class TicketSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    match_id = serializers.IntegerField(source="match.id", read_only=True)
    match_label = serializers.SerializerMethodField()
    match_date = serializers.DateTimeField(source="match.match_date", read_only=True)
    venue = serializers.CharField(source="match.venue", read_only=True)
    competition_name = serializers.CharField(
        source="match.competition.name", read_only=True
    )
    home_club_name = serializers.CharField(
        source="match.home_club.name", read_only=True
    )
    away_club_name = serializers.CharField(
        source="match.away_club.name", read_only=True
    )
    home_club_logo_url = serializers.SerializerMethodField()
    away_club_logo_url = serializers.SerializerMethodField()
    qr_payload = serializers.CharField(read_only=True)
    qr_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_code",
            "qr_payload",
            "qr_image_url",
            "order",
            "ticket_type",
            "ticket_type_name",
            "match_id",
            "match_label",
            "match_date",
            "venue",
            "competition_name",
            "home_club_name",
            "away_club_name",
            "home_club_logo_url",
            "away_club_logo_url",
            "owner",
            "status",
            "issued_at",
            "used_at",
            "checked_in_by",
        ]
        read_only_fields = fields

    def build_absolute_media_url(self, value):
        if not value:
            return ""

        request = self.context.get("request")
        try:
            url = value.url
        except ValueError:
            return ""

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_home_club_logo_url(self, obj):
        return self.build_absolute_media_url(obj.match.home_club.logo)

    def get_away_club_logo_url(self, obj):
        return self.build_absolute_media_url(obj.match.away_club.logo)

    def get_match_label(self, obj):
        return str(obj.match)

    def get_qr_image_url(self, obj):
        request = self.context.get("request")
        path = f"/api/ticketing/tickets/{obj.id}/qr/"

        if request:
            return request.build_absolute_uri(path)

        return path


class TicketValidationSerializer(serializers.Serializer):
    scanned_code = serializers.CharField(max_length=120)
    match_id = serializers.IntegerField(required=False)


class TicketValidationResultSerializer(serializers.ModelSerializer):
    ticket_code = serializers.SerializerMethodField()

    class Meta:
        model = TicketValidationLog
        fields = [
            "id",
            "result",
            "message",
            "scanned_code",
            "ticket_code",
            "match",
            "scanned_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_ticket_code(self, obj):
        if obj.ticket is None:
            return None
        return str(obj.ticket.ticket_code)


class ExpireTicketReservationsSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(default=False, required=False)
