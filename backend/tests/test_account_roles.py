import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import (
    Club,
    FeedItem,
    Follow,
    InterestPreference,
    NotificationPreference,
    PaymentHistory,
    Wallet,
)

User = get_user_model()


@pytest.fixture
def user_model():
    return get_user_model()


def create_user(User, email="fan@example.com", role=User.Role.FAN):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        first_name="Test",
        last_name="User",
        role=role,
    )


@pytest.fixture
def authenticated_client(db):
    User = get_user_model()
    user = create_user(User)
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


# ---------------------------------------------------------------------------
# Tests: Follow Model
# ---------------------------------------------------------------------------


class TestFollowModel:
    def test_create_follow(self, db):
        User = get_user_model()
        user = create_user(User)
        Follow.objects.create(
            user=user, content_type=Follow.ContentType.CLUB, object_id=1
        )
        assert Follow.objects.count() == 1
        assert str(Follow.objects.first()) == f"{user.email} follows CLUB#1"

    def test_unique_constraint(self, db):
        User = get_user_model()
        user = create_user(User)
        Follow.objects.create(
            user=user, content_type=Follow.ContentType.CLUB, object_id=1
        )
        with pytest.raises(Exception):
            Follow.objects.create(
                user=user, content_type=Follow.ContentType.CLUB, object_id=1
            )

    def test_followed_object_for_club(self, db):
        User = get_user_model()
        user = create_user(User)
        club = Club.objects.create(name="Test FC", slug="test-fc")
        follow = Follow.objects.create(
            user=user, content_type=Follow.ContentType.CLUB, object_id=club.id
        )
        obj = follow.followed_object
        assert obj is not None
        assert obj.name == "Test FC"


# ---------------------------------------------------------------------------
# Tests: NotificationPreference Model
# ---------------------------------------------------------------------------


class TestNotificationPreferenceModel:
    def test_create_preferences(self, db):
        User = get_user_model()
        user = create_user(User)
        pref = NotificationPreference.objects.create(
            user=user,
            event_type=NotificationPreference.EventType.MATCH_REMINDER,
        )
        assert pref.email_enabled is True
        assert pref.push_enabled is True
        assert pref.sms_enabled is False

    def test_unique_together(self, db):
        User = get_user_model()
        user = create_user(User)
        NotificationPreference.objects.create(
            user=user, event_type=NotificationPreference.EventType.MATCH_REMINDER
        )
        with pytest.raises(Exception):
            NotificationPreference.objects.create(
                user=user,
                event_type=NotificationPreference.EventType.MATCH_REMINDER,
            )


# ---------------------------------------------------------------------------
# Tests: InterestPreference Model
# ---------------------------------------------------------------------------


class TestInterestPreferenceModel:
    def test_create_interest_preferences(self, db):
        User = get_user_model()
        user = create_user(User)
        pref = InterestPreference.objects.create(user=user)
        assert pref.interested_in_clubs is True
        assert pref.profile_visibility == InterestPreference.PrivacyLevel.PUBLIC

    def test_one_to_one_with_user(self, db):
        User = get_user_model()
        user = create_user(User)
        InterestPreference.objects.create(user=user)
        with pytest.raises(Exception):
            InterestPreference.objects.create(user=user)


# ---------------------------------------------------------------------------
# Tests: Wallet Model
# ---------------------------------------------------------------------------


class TestWalletModel:
    def test_create_wallet(self, db):
        User = get_user_model()
        user = create_user(User)
        wallet = Wallet.objects.create(user=user)
        assert wallet.balance == 0.00
        assert wallet.currency == "UGX"

    def test_one_to_one_with_user(self, db):
        User = get_user_model()
        user = create_user(User)
        Wallet.objects.create(user=user)
        with pytest.raises(Exception):
            Wallet.objects.create(user=user)


# ---------------------------------------------------------------------------
# Tests: PaymentHistory Model
# ---------------------------------------------------------------------------


class TestPaymentHistoryModel:
    def test_create_payment(self, db):
        User = get_user_model()
        user = create_user(User)
        payment = PaymentHistory.objects.create(
            user=user,
            payment_type=PaymentHistory.PaymentType.DEPOSIT,
            amount=100.00,
            reference="TXN-001",
        )
        assert payment.status == PaymentHistory.PaymentStatus.PENDING
        assert str(payment) == f"{user.email} - DEPOSIT - 100.00 UGX"


# ---------------------------------------------------------------------------
# Tests: FeedItem Model
# ---------------------------------------------------------------------------


class TestFeedItemModel:
    def test_create_feed_item(self, db):
        User = get_user_model()
        user = create_user(User)
        item = FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Express FC 2-1 Vipers SC",
            description="Match result update",
            relevance_score=0.9,
        )
        assert item.is_read is False
        assert item.relevance_score == 0.9


# ---------------------------------------------------------------------------
# Tests: Follow API
# ---------------------------------------------------------------------------


class TestFollowAPI:
    def test_follow_requires_auth(self, db):
        client = APIClient()
        response = client.get("/api/accounts/follow/")
        assert response.status_code in (401, 403)

    def test_follow_club(self, authenticated_client):
        client, user = authenticated_client
        club = Club.objects.create(name="Kampala City FC", slug="kampala-city-fc")
        response = client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        assert response.status_code == 201
        assert response.data["content_type"] == "CLUB"
        assert response.data["object_id"] == club.id

    def test_follow_duplicate_returns_409(self, authenticated_client):
        client, user = authenticated_client
        club = Club.objects.create(name="Vipers SC", slug="vipers-sc")
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        response = client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        assert response.status_code == 409

    def test_unfollow(self, authenticated_client):
        client, user = authenticated_client
        club = Club.objects.create(name="Express FC", slug="express-fc")
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        response = client.delete(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["detail"] == "Successfully unfollowed."

    def test_unfollow_non_existent_returns_404(self, authenticated_client):
        client, user = authenticated_client
        response = client.delete(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": 99999},
            format="json",
        )
        assert response.status_code == 404

    def test_list_follows(self, authenticated_client):
        client, user = authenticated_client
        club = Club.objects.create(name="URA FC", slug="ura-fc")
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        response = client.get("/api/accounts/follow/")
        assert response.status_code == 200
        assert response.data["club_count"] >= 1

    def test_check_follow(self, authenticated_client):
        client, user = authenticated_client
        club = Club.objects.create(name="KCCA FC", slug="kcca-fc")
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        response = client.get(f"/api/accounts/follow/check/CLUB/{club.id}/")
        assert response.status_code == 200
        assert response.data["is_following"] is True


# ---------------------------------------------------------------------------
# Tests: Notification Preferences API
# ---------------------------------------------------------------------------


class TestNotificationPreferencesAPI:
    def test_get_notification_preferences(self, authenticated_client):
        client, user = authenticated_client
        response = client.get("/api/accounts/notifications/")
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) > 0

    def test_update_notification_preference(self, authenticated_client):
        client, user = authenticated_client
        response = client.put(
            "/api/accounts/notifications/",
            {
                "event_type": "MATCH_REMINDER",
                "email_enabled": False,
            },
            format="json",
        )
        assert response.status_code == 200
        assert len(response.data["updated"]) >= 1


# ---------------------------------------------------------------------------
# Tests: Interest Preferences API
# ---------------------------------------------------------------------------


class TestInterestPreferencesAPI:
    def test_get_interest_preferences(self, authenticated_client):
        client, user = authenticated_client
        response = client.get("/api/accounts/interests/")
        assert response.status_code == 200
        assert response.data["interested_in_clubs"] is True

    def test_update_interest_preferences(self, authenticated_client):
        client, user = authenticated_client
        response = client.patch(
            "/api/accounts/interests/",
            {"interested_in_transfers": True, "profile_visibility": "PRIVATE"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["interested_in_transfers"] is True
        assert response.data["profile_visibility"] == "PRIVATE"


# ---------------------------------------------------------------------------
# Tests: Wallet API
# ---------------------------------------------------------------------------


class TestWalletAPI:
    def test_get_wallet(self, authenticated_client):
        client, user = authenticated_client
        response = client.get("/api/accounts/wallet/")
        assert response.status_code == 200
        assert response.data["balance"] == "0.00"
        assert response.data["currency"] == "UGX"


# ---------------------------------------------------------------------------
# Tests: Payment History API
# ---------------------------------------------------------------------------


class TestPaymentHistoryAPI:
    def test_get_payments_empty(self, authenticated_client):
        client, user = authenticated_client
        response = client.get("/api/accounts/payments/")
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_get_payments_with_data(self, authenticated_client):
        client, user = authenticated_client
        PaymentHistory.objects.create(
            user=user,
            payment_type=PaymentHistory.PaymentType.DEPOSIT,
            amount=50000.00,
            reference="TXN-123",
            status=PaymentHistory.PaymentStatus.COMPLETED,
        )
        response = client.get("/api/accounts/payments/")
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["amount"] == "50000.00"


# ---------------------------------------------------------------------------
# Tests: Feed API
# ---------------------------------------------------------------------------


class TestFeedAPI:
    def test_get_feed_empty(self, authenticated_client):
        client, user = authenticated_client
        response = client.get("/api/accounts/feed/")
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_get_feed_with_items(self, authenticated_client):
        client, user = authenticated_client
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Test Match Result",
            relevance_score=0.8,
        )
        response = client.get("/api/accounts/feed/")
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_feed_filter_by_type(self, authenticated_client):
        client, user = authenticated_client
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Result",
            relevance_score=0.8,
        )
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.NEWS,
            title="News Item",
            relevance_score=0.5,
        )
        response = client.get("/api/accounts/feed/?item_type=NEWS")
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_feed_unread_only(self, authenticated_client):
        client, user = authenticated_client
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Unread Result",
            relevance_score=0.8,
            is_read=False,
        )
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.NEWS,
            title="Read News",
            relevance_score=0.5,
            is_read=True,
        )
        response = client.get("/api/accounts/feed/?unread_only=true")
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_mark_feed_item_read(self, authenticated_client):
        client, user = authenticated_client
        item = FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Test",
            relevance_score=0.8,
        )
        response = client.post(f"/api/accounts/feed/mark-read/{item.id}/")
        assert response.status_code == 200

    def test_mark_all_feed_read(self, authenticated_client):
        client, user = authenticated_client
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Item 1",
            relevance_score=0.8,
        )
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.NEWS,
            title="Item 2",
            relevance_score=0.5,
        )
        response = client.post("/api/accounts/feed/mark-all-read/")
        assert response.status_code == 200
        assert "2" in response.data["detail"]

    def test_unread_count(self, authenticated_client):
        client, user = authenticated_client
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Unread",
            relevance_score=0.8,
        )
        response = client.get("/api/accounts/feed/unread-count/")
        assert response.status_code == 200
        assert response.data["unread_count"] >= 1


# ---------------------------------------------------------------------------
# Tests: Follow Service
# ---------------------------------------------------------------------------


class TestFollowService:
    def test_follow_entity(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import follow_entity

        follow, created = follow_entity(user, "CLUB", 1)
        assert created is True
        assert follow.user == user

    def test_unfollow_entity(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import follow_entity, unfollow_entity

        follow_entity(user, "CLUB", 1)
        deleted = unfollow_entity(user, "CLUB", 1)
        assert deleted is True

    def test_is_following(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import follow_entity, is_following

        follow_entity(user, "CLUB", 1)
        assert is_following(user, "CLUB", 1) is True
        assert is_following(user, "CLUB", 2) is False

    def test_get_user_follows(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import follow_entity, get_user_follows

        follow_entity(user, "CLUB", 1)
        result = get_user_follows(user)
        assert result["club_count"] == 1


# ---------------------------------------------------------------------------
# Tests: Feed Service
# ---------------------------------------------------------------------------


class TestFeedService:
    def test_create_feed_item(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import create_feed_item

        item = create_feed_item(
            user, FeedItem.ItemType.MATCH_RESULT, "Test", relevance_score=0.9
        )
        assert item.title == "Test"

    def test_aggregate_feed(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import aggregate_feed, create_feed_item

        create_feed_item(user, FeedItem.ItemType.MATCH_RESULT, "A", relevance_score=0.5)
        create_feed_item(user, FeedItem.ItemType.NEWS, "B", relevance_score=0.9)
        items, total = aggregate_feed(user)
        assert total == 2
        # B should come first (higher relevance)
        assert items[0].title == "B"

    def test_mark_feed_item_read(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import create_feed_item, mark_feed_item_read

        item = create_feed_item(user, FeedItem.ItemType.MATCH_RESULT, "Test")
        result = mark_feed_item_read(user, item.id)
        assert result is True

    def test_mark_all_feed_read(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import create_feed_item, mark_all_feed_read

        create_feed_item(user, FeedItem.ItemType.MATCH_RESULT, "A")
        create_feed_item(user, FeedItem.ItemType.NEWS, "B")
        count = mark_all_feed_read(user)
        assert count == 2

    def test_unread_feed_count(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import create_feed_item, get_unread_feed_count

        create_feed_item(user, FeedItem.ItemType.MATCH_RESULT, "A")
        create_feed_item(user, FeedItem.ItemType.NEWS, "B", relevance_score=0.0)
        count = get_unread_feed_count(user)
        assert count == 2


# ---------------------------------------------------------------------------
# Tests: Wallet & Payment Services
# ---------------------------------------------------------------------------


class TestWalletServices:
    def test_get_or_create_wallet(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import get_or_create_wallet

        wallet = get_or_create_wallet(user)
        assert wallet.balance == 0.00

    def test_get_payment_history(self, db, user_model):
        User = user_model
        user = create_user(User)
        from accounts.services import get_payment_history

        PaymentHistory.objects.create(
            user=user,
            payment_type=PaymentHistory.PaymentType.DEPOSIT,
            amount=100.00,
            reference="REF-1",
        )
        items, total = get_payment_history(user)
        assert total == 1
