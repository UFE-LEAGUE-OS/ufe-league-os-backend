import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from engagements.models import Poll, PollOption, PollVote, Sport


@pytest.fixture
def poll_vote_context(db):
    User = get_user_model()
    user = User.objects.create_user(
        email="poll-voter@example.com",
        password="testpass123",
        first_name="Poll",
        last_name="Voter",
        role=User.Role.FAN,
        is_email_verified=True,
    )
    sport = Sport.objects.create(name="Poll Football", sport_type="football")
    poll = Poll.objects.create(
        title="Current poll",
        sport=sport,
        created_by=user,
    )
    option = PollOption.objects.create(poll=poll, label="Option one")
    other_poll = Poll.objects.create(
        title="Other poll",
        sport=sport,
        created_by=user,
    )
    other_option = PollOption.objects.create(poll=other_poll, label="Other option")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, poll, option, other_poll, other_option


def test_valid_poll_vote_creates_vote_and_increments_count(poll_vote_context):
    client, user, poll, option, _other_poll, _other_option = poll_vote_context

    response = client.post(
        reverse("engagements-poll-vote", args=[poll.id]),
        {"option": option.id},
        format="json",
    )

    assert response.status_code == 201
    assert (
        PollVote.objects.filter(
            poll=poll,
            option=option,
            voter=user,
        ).count()
        == 1
    )
    option.refresh_from_db()
    assert option.vote_count == 1


def test_duplicate_vote_for_same_poll_is_rejected(poll_vote_context):
    client, _user, poll, option, _other_poll, _other_option = poll_vote_context
    url = reverse("engagements-poll-vote", args=[poll.id])
    assert client.post(url, {"option": option.id}, format="json").status_code == 201

    response = client.post(url, {"option": option.id}, format="json")

    assert response.status_code == 400
    assert PollVote.objects.filter(poll=poll).count() == 1


def test_option_from_another_poll_is_rejected(poll_vote_context):
    client, _user, poll, _option, _other_poll, other_option = poll_vote_context

    response = client.post(
        reverse("engagements-poll-vote", args=[poll.id]),
        {"poll": other_option.poll_id, "option": other_option.id},
        format="json",
    )

    assert response.status_code == 400
    assert PollVote.objects.count() == 0


def test_unauthenticated_poll_vote_is_rejected(poll_vote_context):
    _client, _user, poll, option, _other_poll, _other_option = poll_vote_context

    response = APIClient().post(
        reverse("engagements-poll-vote", args=[poll.id]),
        {"option": option.id, "voter_id": 999},
        format="json",
    )

    assert response.status_code in (401, 403)
    assert PollVote.objects.count() == 0
