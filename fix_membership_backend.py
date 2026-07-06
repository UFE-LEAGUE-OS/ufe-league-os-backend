from pathlib import Path

serializers_path = Path("backend/memberships/serializers.py")
views_path = Path("backend/memberships/views.py")

serializers = serializers_path.read_text()

start = serializers.find("class MembershipSubscriptionSerializer(serializers.ModelSerializer):")
end = serializers.find("\n\nclass MembershipPaymentSerializer", start)

new_serializer = '''class MembershipSubscriptionSerializer(serializers.ModelSerializer):
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

        return MembershipCardSerializer(card, context=self.context).data'''

if start == -1 or end == -1:
    raise SystemExit("Could not find MembershipSubscriptionSerializer")

serializers = serializers[:start] + new_serializer + serializers[end:]
serializers_path.write_text(serializers)

views = views_path.read_text()

views = views.replace(
'''def membership_card_view(request):
    subscription = _get_active_subscription_for_user(request.user)

    if subscription is None:''',
'''def membership_card_view(request):
    subscription_id = request.data.get("subscription") or request.query_params.get("subscription")

    if subscription_id:
        subscription = (
            MembershipSubscription.objects.filter(
                id=subscription_id,
                user=request.user,
                status=MembershipSubscription.Status.ACTIVE,
            )
            .select_related("plan", "club")
            .first()
        )
    else:
        subscription = _get_active_subscription_for_user(request.user)

    if subscription is None:''',
)

views = views.replace(
'''subscriptions = MembershipSubscription.objects.select_related(
            "user", "plan", "club"
        )''',
'''subscriptions = MembershipSubscription.objects.select_related(
            "user", "plan", "club", "membership_card"
        )''',
)

views = views.replace(
'''queryset = MembershipPayment.objects.select_related(
        "subscription", "subscription_plan"
    )''',
'''queryset = MembershipPayment.objects.select_related(
        "subscription",
        "subscription__user",
        "subscription__plan",
        "subscription__club",
        "subscription_plan",
    )''',
)

views_path.write_text(views)

print("Backend membership multi-card fixes applied.")
