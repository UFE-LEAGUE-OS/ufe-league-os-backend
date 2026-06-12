from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


def test_roles_endpoint_returns_all_roles(db):
    client = APIClient()
    url = reverse("roles")

    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "roles" in response.data
    assert len(response.data["roles"]) == 8

    expected_labels = {
        "Fan / Member",
        "Club Admin",
        "League Admin",
        "Union / Federation Admin",
        "Super Admin",
        "Referee / Match Official",
        "Ticketing Officer",
        "Sponsor",
    }

    returned_labels = {item["label"] for item in response.data["roles"]}
    assert expected_labels == returned_labels

    assert any(item["key"] == "FAN" for item in response.data["roles"])
    assert any(item["key"] == "SUPER_ADMIN" for item in response.data["roles"])
