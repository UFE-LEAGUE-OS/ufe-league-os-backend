from django.test import TestCase


class MembershipSmokeTests(TestCase):
    def test_import_models(self):
        from memberships.models import (
            MembershipCard,
            MembershipPayment,
            MembershipPlan,
            MembershipSubscription,
        )

        self.assertIsNotNone(MembershipPlan)
        self.assertIsNotNone(MembershipSubscription)
        self.assertIsNotNone(MembershipPayment)
        self.assertIsNotNone(MembershipCard)