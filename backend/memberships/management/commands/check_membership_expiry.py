from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from memberships.models import MembershipCard, MembershipSubscription


class Command(BaseCommand):
    help = (
        "Check for expiring and expired memberships "
        "and update card statuses accordingly."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        soon_expiry_threshold = now + timedelta(days=7)

        expiring_subscriptions = MembershipSubscription.objects.filter(
            status=MembershipSubscription.Status.ACTIVE,
            ends_at__lte=soon_expiry_threshold,
            ends_at__gt=now,
        )

        for subscription in expiring_subscriptions:
            self.stdout.write(
                f"Membership expiring soon: {subscription} (ends {subscription.ends_at})"
            )

        expired_subscriptions = MembershipSubscription.objects.filter(
            status=MembershipSubscription.Status.ACTIVE,
            ends_at__lte=now,
        )

        updated_cards = 0
        updated_subscriptions = 0

        for subscription in expired_subscriptions:
            subscription.status = MembershipSubscription.Status.EXPIRED
            subscription.save(update_fields=["status", "updated_at"])

            card = getattr(subscription, "membership_card", None)
            if card and card.status == MembershipCard.CardStatus.ACTIVE:
                card.status = MembershipCard.CardStatus.EXPIRED
                card.save(update_fields=["status"])

            updated_subscriptions += 1
            updated_cards += 1
            self.stdout.write(f"Expired: {subscription}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {expiring_subscriptions.count()} expiring and "
                f"{updated_subscriptions} expired memberships."
            )
        )
