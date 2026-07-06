from rest_framework import serializers

from .models import (
    MembershipCard,
    MembershipPayment,
    MembershipPlan,
    MembershipSubscription,
)


class MembershipPlanSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)

    class Meta:
        model = MembershipPlan
        fields = [
            "id",
            "club",
            "club_name",
            "name",
            "description",
            "tier",
            "billing_cycle",
            "price_amount",
            "currency",
            "benefits",
            "is_active",
            "is_visible",
            "created_at",
            "updated_at",
        ]


class MembershipSubscriptionSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    club_slug = serializers.CharField(source="club.slug", read_only=True)
    club_logo_url = serializers.SerializerMethodField()
    card = serializers.SerializerMethodField()

    class Meta:
        model = MembershipSubscription
        fields = [
            "id",
            "user",
            "user_email",
            "plan",
            "plan_name",
            "club",
            "club_name",
            "club_slug",
            "club_logo_url",
            "status",
            "starts_at",
            "ends_at",
            "created_at",
            "updated_at",
            "card",
        ]

    def get_club_logo_url(self, obj):
        logo = getattr(obj.club, "logo", None)
        if not logo:
            return ""

        try:
            url = logo.url
        except ValueError:
            return ""

        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_card(self, obj):
        card = getattr(obj, "membership_card", None)
        if not card:
            return None

        return MembershipCardSerializer(card, context=self.context).data


class MembershipPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPayment
        fields = [
            "id",
            "subscription",
            "subscription_plan",
            "amount_paid",
            "currency",
            "payment_method",
            "provider",
            "transaction_reference",
            "provider_transaction_id",
            "provider_status",
            "provider_response",
            "checkout_url",
            "paid_at",
            "status",
            "created_at",
            "updated_at",
        ]


class MembershipCardSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)

    class Meta:
        model = MembershipCard
        fields = [
            "id",
            "subscription",
            "user",
            "user_email",
            "club",
            "club_name",
            "card_number",
            "qr_code_data",
            "tier",
            "billing_cycle",
            "issued_at",
            "valid_from",
            "valid_until",
            "status",
            "metadata",
        ]
