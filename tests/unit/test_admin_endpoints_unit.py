import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1.endpoints import admin as admin_endpoints
from app.core.config import settings
from app.services import admin_delivery_service
from app.services import notification_service
from app.services import trip_service
from app.services import user_service as crud_user


def _as_admin():
    return {"id": "admin-1", "role": "admin", "name": "Admin"}


@pytest.fixture
def client(request):
    """
    Minimal app for unit tests: mount ONLY the admin router.
    This avoids importing the full `app.main` (which imports all routers).
    """
    app = FastAPI()
    app.include_router(admin_endpoints.router, prefix=f"{settings.API_V1_STR}/admin")
    request.node._fastapi_app_under_test = app
    return TestClient(app)


def test_admin_list_boat_owners_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(
        crud_user,
        "get_boat_owners",
        lambda: [{"id": "bo-1", "name": "Boat Owner 1"}],
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/boat-owners")

    assert resp.status_code == 200
    assert resp.json() == {
        "success": True,
        "boat_owners": [{"id": "bo-1", "name": "Boat Owner 1"}],
    }


def test_admin_dashboard_quick_snapshot_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(
        crud_user,
        "get_admin_dashboard_role_counts",
        lambda: {
            "counts": {"boat_owner": 42, "officer": 28, "agent": 42, "buyer": 28},
            "updated_at": "2026-03-18T00:00:00Z",
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/dashboard")

    assert resp.status_code == 200
    assert resp.json() == {
        "success": True,
        "user": {"id": "admin-1", "name": "Admin"},
        "quick_snapshot": {
            "boat_owners": 42,
            "harbour_officers": 28,
            "agents": 42,
            "buyers": 28,
        },
        "updated_at": "2026-03-18T00:00:00Z",
    }


def test_admin_get_boat_owner_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(crud_user, "get_user_by_id", lambda _id: None)

    resp = client.get(f"{settings.API_V1_STR}/admin/boat-owners/does-not-exist")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat owner not found"


def test_admin_update_boat_owner_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(crud_user, "get_user_by_id", lambda _id: {"id": _id, "role": "boat_owner"})
    monkeypatch.setattr(crud_user, "update_user", lambda _id, update_dict: True)

    resp = client.put(
        f"{settings.API_V1_STR}/admin/boat-owners/bo-1",
        json={"name": "New Name", "phone": "9999999999"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Boat owner updated successfully"}


def test_admin_delete_boat_owner_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(crud_user, "get_user_by_id", lambda _id: {"id": _id, "role": "boat_owner"})
    monkeypatch.setattr(crud_user, "delete_user", lambda _id: True)

    resp = client.delete(f"{settings.API_V1_STR}/admin/boat-owners/bo-1")

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Boat owner deleted successfully"}


def test_admin_create_officer_duplicate_email_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(crud_user, "get_user_by_identifier", lambda _email: {"id": "u-1"})

    resp = client.post(
        f"{settings.API_V1_STR}/admin/officers",
        json={
            "name": "Officer",
            "email": "officer@example.com",
            "password": "pw",
            "phone": "9999999999",
        },
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "User with this email already exists"


def test_admin_create_officer_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(crud_user, "get_user_by_identifier", lambda _email: None)
    monkeypatch.setattr(crud_user, "get_role_id_by_name", lambda _role: "role-officer")
    monkeypatch.setattr(crud_user, "create_officer_user", lambda _data, _role_id: "officer-1")

    resp = client.post(
        f"{settings.API_V1_STR}/admin/officers",
        json={
            "name": "Officer",
            "email": "officer@example.com",
            "password": "pw",
            "phone": "9999999999",
        },
    )

    assert resp.status_code == 201
    assert resp.json() == {
        "success": True,
        "user_id": "officer-1",
        "message": "Officer account created successfully",
    }


def test_admin_notifications_default_params(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    captured = {}

    def fake_list_admin_notifications(limit: int = 50, unread_only: bool = False):
        captured["limit"] = limit
        captured["unread_only"] = unread_only
        return [{"id": "n-1"}]

    monkeypatch.setattr(
        notification_service,
        "list_admin_notifications",
        fake_list_admin_notifications,
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/notifications")

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "notifications": [{"id": "n-1"}]}
    assert captured == {"limit": 50, "unread_only": False}


def test_admin_notifications_query_params(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    captured = {}

    def fake_list_admin_notifications(limit: int = 50, unread_only: bool = False):
        captured["limit"] = limit
        captured["unread_only"] = unread_only
        return []

    monkeypatch.setattr(
        notification_service,
        "list_admin_notifications",
        fake_list_admin_notifications,
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/notifications?limit=10&unread_only=true")

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "notifications": []}
    assert captured == {"limit": 10, "unread_only": True}


def test_admin_notifications_limit_0_becomes_50(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    captured = {}

    def fake_list_admin_notifications(limit: int = 50, unread_only: bool = False):
        captured["limit"] = limit
        captured["unread_only"] = unread_only
        return []

    monkeypatch.setattr(
        notification_service,
        "list_admin_notifications",
        fake_list_admin_notifications,
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/notifications?limit=0")

    assert resp.status_code == 200
    assert captured == {"limit": 50, "unread_only": False}


def test_admin_list_agents_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    captured = {}

    def fake_get_agents_paginated(search, limit, offset):
        captured["search"] = search
        captured["limit"] = limit
        captured["offset"] = offset
        return ([{"id": "agent-1", "name": "Agent"}], 1)

    monkeypatch.setattr(crud_user, "get_agents_paginated", fake_get_agents_paginated)

    resp = client.get(f"{settings.API_V1_STR}/admin/agents?search=foo&page=2&page_size=10")

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["agents"] == [{"id": "agent-1", "name": "Agent"}]
    assert resp.json()["total"] == 1
    assert captured == {"search": "foo", "limit": 10, "offset": 10}


def test_admin_list_agents_page_validation_400(client):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    resp = client.get(f"{settings.API_V1_STR}/admin/agents?page=0")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "page must be >= 1"


def test_admin_list_buyers_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    def fake_get_buyers_paginated(search, limit, offset):
        return (
            [{"id": "buyer-1", "name": "Buyer", "phone": "9999999999", "email": "b@example.com"}],
            1,
        )

    monkeypatch.setattr(crud_user, "get_buyers_paginated", fake_get_buyers_paginated)

    resp = client.get(f"{settings.API_V1_STR}/admin/buyers?page=1&page_size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] == 1
    assert body["buyers"] == [{"id": "buyer-1", "name": "Buyer", "phone": "9999999999", "email": "b@example.com"}]


def test_admin_list_buyers_page_size_validation_400(client):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    resp = client.get(f"{settings.API_V1_STR}/admin/buyers?page_size=0")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "page_size must be >= 1"


def test_admin_list_buyer_deliveries_invalid_status_400(client):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    resp = client.get(f"{settings.API_V1_STR}/admin/buyers/buyer-1/deliveries?status=bad")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid status. Allowed values: pending, completed"


def test_admin_list_buyer_deliveries_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    delivery = {
        "delivery_id": "d-1",
        "auction_identifier": "A-1",
        "location": "Mumbai",
        "status": "completed",
        "fish_type": "tuna",
        "bid_price": 10.0,
        "auction_type": "english",
        "start_time": "2026-01-01T00:00:00Z",
        "my_bid": 10.0,
        "required_quantity": 5.0,
        "delivered_quantity": 5.0,
        "sale": 50.0,
        "delivery_status": "completed",
        "delivered_at": None,
    }

    monkeypatch.setattr(
        admin_delivery_service,
        "list_buyer_deliveries_for_admin",
        lambda buyer_id, status_filter: [delivery],
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/buyers/buyer-1/deliveries?status=completed")

    assert resp.status_code == 200
    assert resp.json() == [delivery]


def test_admin_list_boats_enriches_status_fields(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    boats = [{"id": "boat-1", "boat_name": "B1"}]
    monkeypatch.setattr(crud_user, "get_all_boats", lambda boat_owner_id=None: boats)
    monkeypatch.setattr(
        trip_service,
        "get_boat_trip_status",
        lambda boat_id: {"trip_status": "sailing", "latest_movement_id": "m-1", "movement_type": "departure"},
    )

    resp = client.get(f"{settings.API_V1_STR}/admin/boats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["boats"][0]["id"] == "boat-1"
    assert body["boats"][0]["boat_status"] == "At sea"
    assert body["boats"][0]["latest_movement_id"] == "m-1"
    assert body["boats"][0]["latest_movement_status"] == "departure"


def test_admin_get_boat_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin
    monkeypatch.setattr(crud_user, "get_boat_by_id", lambda _id: None)

    resp = client.get(f"{settings.API_V1_STR}/admin/boats/boat-404")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat not found"


def test_admin_get_boat_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin
    monkeypatch.setattr(crud_user, "get_boat_by_id", lambda _id: {"id": _id, "boat_name": "B"})

    resp = client.get(f"{settings.API_V1_STR}/admin/boats/boat-1")

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "boat": {"id": "boat-1", "boat_name": "B"}}


def test_admin_officer_crew_history_page_validation_400(client):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    resp = client.get(f"{settings.API_V1_STR}/admin/officers/off-1/crew-history?page=0")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "page must be >= 1"


def test_admin_officer_crew_history_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_user] = _as_admin

    monkeypatch.setattr(
        trip_service,
        "get_registered_crew_history",
        lambda officer_user_id, date_filter, is_register, offset, limit: [
            {
                "crew_id": "c-1",
                "crew_name": "Crew",
                "phone_number": "999",
                "emergency_contact_number": None,
                "aadhaar_number": None,
                "is_register": True,
                "movement_at": "2026-01-01T00:00:00Z",
                "image_url": None,
            }
        ],
    )

    resp = client.get(
        f"{settings.API_V1_STR}/admin/officers/off-1/crew-history?date_filter=today&page=1&page_size=10"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["date_filter"] == "today"
    assert body["total_records"] == 1
    assert body["records"][0]["crew_id"] == "c-1"

