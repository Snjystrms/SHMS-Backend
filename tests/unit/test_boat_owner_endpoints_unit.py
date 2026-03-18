import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1.endpoints import boat_owners as boat_owner_endpoints
from app.core.config import settings


def _as_boat_owner():
    return {"id": "bo-1", "role": "boat_owner", "name": "Boat Owner"}


def _as_agent():
    return {"id": "agent-1", "role": "agent", "name": "Agent"}


def _auction_dict(auction_id: str, seller_id: str):
    # Must satisfy `app.schemas.auction.Auction` response_model.
    return {
        "id": auction_id,
        "seller_id": seller_id,
        "fish_name": "Pomfret",
        "initial_price": 100.0,
        "current_price": 120.0,
        "sale": None,
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": None,
        "status": "scheduled",
        "winner_id": None,
        "bidding_request_id": None,
        "movement_id": None,
        "auction_type": "open_box",
    }


def _delivery_detail(auction_id: str):
    # Must satisfy both ScanDeliveryResponse and InitiateDeliveryResponse.
    return {
        "auction_id": auction_id,
        "buyer_name": "Buyer",
        "bid_price": 150.0,
        "auction_type": "open_box",
        "requested_quantity": 10.0,
        "delivered_quantity": 0.0,
        "delivery_status": "pending",
        "delivered_at": None,
        "delivery_recorded_by": None,
        "fish_type": "Pomfret",
        "start_time": "2026-01-01T00:00:00Z",
        "auction_identifier": "AUC-001",
        "is_already_delivered": False,
    }


def _pending_delivery_item(auction_id: str, status: str = "pending"):
    # Must satisfy `PendingDeliveryItem` (list response_model for /deliveries).
    return {
        **_delivery_detail(auction_id),
        "status": status,
    }


def _bidding_request_dict(request_id: str, status: str):
    return {
        "id": request_id,
        "boat_id": "boat-1",
        "boat_number": "MH-1",
        "boat_name": "Boat",
        "agent_id": "agent-1",
        "agent_name": "Agent",
        "status": status,
        "note": None,
        "created_at": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def client(request):
    """
    Minimal app for unit tests: mount ONLY the boat-owners router.
    Avoid importing `app.main` which mounts all routers.
    """
    app = FastAPI()
    app.include_router(boat_owner_endpoints.router, prefix=f"{settings.API_V1_STR}/boat-owners")
    request.node._fastapi_app_under_test = app
    return TestClient(app)


def test_boat_owner_dashboard_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_boat_owner_dashboard",
        lambda _boat_owner_id: {
            "quick_activity": {"departures": 1, "arrivals": 2},
            "pending_auctions": [{"id": "auc-1"}],
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["user"]["id"] == "bo-1"
    assert body["quick_activity"]["departures"] == 1


def test_boat_owner_list_my_auctions_boat_owner_branch(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_boat_owner

    called = {"seller": 0, "agent": 0}

    def list_for_seller(_seller_id):
        called["seller"] += 1
        return [_auction_dict("auc-1", seller_id="bo-1")]

    def list_for_agent(_agent_id):
        called["agent"] += 1
        return [_auction_dict("auc-2", seller_id="bo-1")]

    monkeypatch.setattr(boat_owner_endpoints.auction_service, "list_auctions_for_seller", list_for_seller)
    monkeypatch.setattr(boat_owner_endpoints.auction_service, "list_auctions_for_agent", list_for_agent)

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/auctions")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "auc-1"
    assert called == {"seller": 1, "agent": 0}


def test_boat_owner_list_my_auctions_agent_branch(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_agent

    monkeypatch.setattr(
        boat_owner_endpoints.auction_service,
        "list_auctions_for_agent",
        lambda _id: [_auction_dict("auc-2", seller_id="bo-1")],
    )
    monkeypatch.setattr(
        boat_owner_endpoints.auction_service,
        "list_auctions_for_seller",
        lambda _id: [_auction_dict("auc-x", seller_id="bo-1")],
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/auctions")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "auc-2"


def test_boat_owner_list_my_notifications_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    def fake_list(boat_owner_id, limit, unread_only):
        assert boat_owner_id == "bo-1"
        assert limit == 50
        assert unread_only is True
        return [{"id": "n-1"}]

    monkeypatch.setattr(boat_owner_endpoints.notification_service, "list_boat_owner_notifications", fake_list)

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/notifications?unread_only=true")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "notifications": [{"id": "n-1"}]}


def test_boat_owner_sales_report_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_sales_service,
        "get_sales_report",
        lambda **kwargs: {
            "success": True,
            "total_earning": 0.0,
            "total_records": 0,
            "filter_applied": {"filter": str(kwargs["filter_name"]), "from_date": None, "to_date": None},
            "records": [],
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/sales/report?filter=last_three_months")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_boat_owner_sales_report_value_error_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    def fake_report(**_kwargs):
        raise ValueError("bad filter")

    monkeypatch.setattr(boat_owner_endpoints.boat_owner_sales_service, "get_sales_report", fake_report)

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/sales/report?filter=custom")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad filter"


def test_boat_owner_register_duplicate_name_400(client, monkeypatch):
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "get_boat_owner_by_name", lambda _name: {"id": "bo-x"})

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/register",
        json={"name": " Existing ", "phone": "9999999999"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "A boat owner with this name already exists"


def test_boat_owner_register_success_calls_temp_registration(client, monkeypatch):
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "get_boat_owner_by_name", lambda _name: None)

    captured = {}

    def fake_start_temp_user_registration(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message": "OTP sent"}

    monkeypatch.setattr(boat_owner_endpoints, "start_temp_user_registration", fake_start_temp_user_registration)

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/register",
        json={"name": "  Boat Owner  ", "phone": " 9999999999 "},
    )

    assert resp.status_code == 201
    assert resp.json() == {"success": True, "message": "OTP sent"}
    assert captured["name"] == "Boat Owner"
    assert captured["phone"] == "9999999999"
    assert captured["duplicate_check"] is boat_owner_endpoints.crud_user.get_boat_owner_by_phone


def test_boat_owner_login_send_otp_success(client, monkeypatch):
    def fake_send_otp_for_phone(phone, get_user_by_phone, not_found_detail):
        assert phone == "9999999999"
        assert get_user_by_phone is boat_owner_endpoints.crud_user.get_boat_owner_by_phone
        assert not_found_detail == boat_owner_endpoints.BOAT_OWNER_NOT_FOUND_DETAIL
        return {"masked_mobile": "******9999", "expires_in_minutes": 10}

    monkeypatch.setattr(boat_owner_endpoints, "send_otp_for_phone", fake_send_otp_for_phone)

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/login/send-otp",
        json={"mobile_number": " 9999999999 "},
    )
    assert resp.status_code == 200
    assert resp.json() == {"masked_mobile": "******9999", "expires_in_minutes": 10}


def test_boat_owner_login_verify_success_returns_token_shape(client, monkeypatch):
    monkeypatch.setattr(
        boat_owner_endpoints,
        "verify_otp_and_login_with_role",
        lambda **_kwargs: {"id": "bo-1", "name": "Boat Owner", "email": None, "role": "boat_owner"},
    )
    monkeypatch.setattr(boat_owner_endpoints.security, "create_access_token", lambda **_kwargs: "test.token.value")

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/login/verify",
        json={"mobile_number": "9999999999", "otp": "123456"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "test.token.value"
    assert body["token_type"] == "bearer"
    assert body["user"] == {"id": "bo-1", "name": "Boat Owner", "email": "", "role": "boat_owner"}


def test_boat_owner_list_my_boats_status_mapping(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boats_by_owner_id",
        lambda _id: [{"id": "boat-1"}, {"id": "boat-2"}, {"id": "boat-3"}],
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_boat_trip_statuses",
        lambda _ids: {
            "boat-1": None,
            "boat-2": {"latest_movement_id": "mov-2", "trip_status": "sailing"},
            "boat-3": {"latest_movement_id": "mov-3", "trip_status": "docked"},
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats")
    assert resp.status_code == 200
    boats = resp.json()["boats"]
    assert boats[0]["boat_status"] == "No movement"
    assert boats[1]["boat_status"] == "At sea"
    assert boats[2]["boat_status"] == "At harbour"


def test_boat_owner_create_boat_success_without_document(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(boat_owner_endpoints.crud_user, "create_boat", lambda _owner_id, _data: "boat-1")
    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _boat_id: {"id": _boat_id, "boat_owner_id": "bo-1", "boat_name": "B"},
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/boats",
        data={"boat_name": " B ", "boat_type": " T ", "boat_number": " N ", "harbor_name": "mumbai"},
    )
    assert resp.status_code == 201
    assert resp.json()["success"] is True
    assert resp.json()["boat"]["id"] == "boat-1"


def test_boat_owner_create_boat_failed_500(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(boat_owner_endpoints.crud_user, "create_boat", lambda _owner_id, _data: None)

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/boats",
        data={"boat_name": "B", "boat_type": "T", "boat_number": "N", "harbor_name": "mumbai"},
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to create boat"


def test_boat_owner_create_boat_invalid_document_type_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(boat_owner_endpoints.crud_user, "create_boat", lambda _owner_id, _data: "boat-1")
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "get_boat_by_id", lambda _boat_id: {"id": _boat_id})

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/boats",
        data={"boat_name": "B", "boat_type": "T", "boat_number": "N", "harbor_name": "mumbai"},
        files={"document": ("doc.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 400
    assert "Document must be PDF or image" in resp.json()["detail"]


def test_boat_owner_get_my_boat_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "get_boat_by_id", lambda _id: None)

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-404")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat not found"


def test_boat_owner_get_my_boat_wrong_owner_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-other"},
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-1")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat not found"


def test_boat_owner_get_my_boat_success_no_movement(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )
    monkeypatch.setattr(boat_owner_endpoints.trip_service, "get_boat_trip_status", lambda _id: {})

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-1")
    assert resp.status_code == 200
    boat = resp.json()["boat"]
    assert boat["boat_status"] == "No movement"


def test_boat_owner_trip_details_no_trip_data_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_boat_trip_status",
        lambda _id: {"trip_status": "docked", "latest_movement_id": None},
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-1/trip-details")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No trip data for this boat"


def test_boat_owner_trip_details_at_sea_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1", "boat_number": "MH-1", "boat_name": "B", "boat_type": "T"},
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_boat_trip_status",
        lambda _id: {
            "trip_status": "sailing",
            "latest_movement_id": "mov-1",
            "departure_details": {"departure_at": "2026-01-01T00:00:00Z", "from_port": "mumbai", "crew_count": 2},
        },
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_departure_inventory",
        lambda _movement_id: {"diesel_liters": 10, "ice_blocks": 5, "plastic_bottle_count": 1},
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_departure_crew_with_details",
        lambda _movement_id: [{"id": "c-1", "name": "Crew", "is_pilot": True}],
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-1/trip-details")
    assert resp.status_code == 200
    body = resp.json()
    assert body["view_type"] == "at_sea"
    assert body["boat_id"] == "boat-1"
    assert body["departure"]["from_port"] == "mumbai"
    assert body["total_crew"] == 2


def test_boat_owner_trip_details_departure_details_missing_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_boat_trip_status",
        lambda _id: {
            "trip_status": "sailing",
            "latest_movement_id": "mov-1",
            "departure_details": {"departure_at": None, "from_port": "mumbai"},
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-1/trip-details")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Departure details not found"


def test_boat_owner_trip_details_at_harbour_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1", "boat_number": "MH-1", "boat_name": "B", "boat_type": "T"},
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_boat_trip_status",
        lambda _id: {"trip_status": "arrived", "latest_movement_id": "mov-1"},
    )
    monkeypatch.setattr(
        boat_owner_endpoints.trip_service,
        "get_movement_with_departure_arrival",
        lambda _movement_id, _boat_id: {
            "movement_type": "arrival",
            "movement_at": "2026-01-02T00:00:00Z",
            "departure_at": "2026-01-01T00:00:00Z",
            "harbor_name": "mumbai",
            "port_name": "mumbai",
            "crew_count": 1,
            "partial_arrival_reason": None,
            "partial_arrival_details": None,
        },
    )
    monkeypatch.setattr(boat_owner_endpoints.trip_service, "get_departure_crew_with_details", lambda _id: [])
    monkeypatch.setattr(boat_owner_endpoints.trip_service, "get_departure_inventory", lambda _id: {})

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/boats/boat-1/trip-details")
    assert resp.status_code == 200
    body = resp.json()
    assert body["view_type"] == "at_harbour"
    assert body["trip_status"] == "arrived"


def test_boat_owner_update_my_boat_wrong_owner_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-other"},
    )

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/boats/boat-1",
        data={"boat_name": "New"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat not found"


def test_boat_owner_update_my_boat_success_updates_fields(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )

    captured = {}

    def fake_update_boat(boat_id, update_dict):
        captured["boat_id"] = boat_id
        captured["update_dict"] = update_dict
        return True

    monkeypatch.setattr(boat_owner_endpoints.crud_user, "update_boat", fake_update_boat)
    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1", "boat_name": "New Name"},
    )

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/boats/boat-1",
        data={"boat_name": "  New Name  ", "harbor_name": "  mumbai "},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert captured["boat_id"] == "boat-1"
    assert captured["update_dict"]["boat_name"] == "New Name"


def test_boat_owner_update_my_boat_invalid_document_type_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/boats/boat-1",
        data={"boat_name": "New"},
        files={"document": ("doc.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 400
    assert "Document must be PDF or image" in resp.json()["detail"]


def test_boat_owner_update_my_boat_update_failure_500(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "update_boat", lambda _id, _d: False)

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/boats/boat-1",
        data={"boat_name": "New"},
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to update boat"


def test_boat_owner_delete_my_boat_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "delete_boat", lambda _id: True)

    resp = client.delete(f"{settings.API_V1_STR}/boat-owners/boats/boat-1")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Boat deleted"}


def test_boat_owner_delete_my_boat_delete_failure_500(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.crud_user,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_owner_id": "bo-1"},
    )
    monkeypatch.setattr(boat_owner_endpoints.crud_user, "delete_boat", lambda _id: False)

    resp = client.delete(f"{settings.API_V1_STR}/boat-owners/boats/boat-1")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to delete boat"


def test_boat_owner_scan_delivery_invalid_json_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/scan",
        json={"qr_payload": "not-json"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid qr_payload: expected JSON with auction_id and buyer_id"


def test_boat_owner_scan_delivery_missing_params_400(client):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    resp = client.post(f"{settings.API_V1_STR}/boat-owners/deliveries/scan", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Provide auction_id and buyer_id, or qr_payload"


def test_boat_owner_scan_delivery_forbidden_403(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_delivery_by_qr",
        lambda **_kwargs: (None, "Auction does not belong to this boat owner"),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/scan",
        json={"auction_id": "auc-1", "buyer_id": "buyer-1"},
    )
    assert resp.status_code == 403


def test_boat_owner_scan_delivery_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_delivery_by_qr",
        lambda **_kwargs: (None, "Not found"),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/scan",
        json={"auction_id": "auc-1", "buyer_id": "buyer-1"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not found"


def test_boat_owner_scan_delivery_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_delivery_by_qr",
        lambda **_kwargs: (_delivery_detail("auc-1"), None),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/scan",
        json={"auction_id": "auc-1", "buyer_id": "buyer-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["auction_id"] == "auc-1"


def test_boat_owner_record_delivery_forbidden_403(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "record_delivery",
        lambda **_kwargs: (None, "Auction does not belong to this boat owner"),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/auc-1/record",
        json={"delivered_quantity": 10},
    )
    assert resp.status_code == 403


def test_boat_owner_record_delivery_other_error_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "record_delivery",
        lambda **_kwargs: (None, "Bad request"),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/auc-1/record",
        json={"delivered_quantity": 10},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Bad request"


def test_boat_owner_record_delivery_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "record_delivery",
        lambda **_kwargs: ({}, None),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/boat-owners/deliveries/auc-1/record",
        json={"delivered_quantity": 10},
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Delivery recorded successfully"}


def test_boat_owner_initiate_delivery_agent_branch_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_agent

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction_by_agent",
        lambda **_kwargs: (_delivery_detail("auc-1"), None),
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries/initiate/auc-1")
    assert resp.status_code == 200
    assert resp.json()["auction_id"] == "auc-1"


def test_boat_owner_initiate_delivery_boat_owner_branch_no_winner_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction",
        lambda **_kwargs: (None, "No winner yet"),
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries/initiate/auc-1")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No winner yet"


def test_boat_owner_initiate_delivery_boat_owner_branch_forbidden_403(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction",
        lambda **_kwargs: (None, "Auction does not belong to this boat owner"),
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries/initiate/auc-1")
    assert resp.status_code == 403


def test_boat_owner_initiate_delivery_boat_owner_branch_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction",
        lambda **_kwargs: (None, "Not found"),
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries/initiate/auc-1")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not found"


def test_boat_owner_initiate_delivery_boat_owner_branch_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_or_agent_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction",
        lambda **_kwargs: (_delivery_detail("auc-1"), None),
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries/initiate/auc-1")
    assert resp.status_code == 200
    assert resp.json()["auction_id"] == "auc-1"


def test_boat_owner_list_deliveries_invalid_status_400(client):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner
    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries?status=bad")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid status. Allowed values: pending, completed"


def test_boat_owner_list_deliveries_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.boat_owner_delivery_service,
        "get_deliveries_for_boat_owner",
        lambda **_kwargs: [_pending_delivery_item("auc-1", status="pending")],
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/deliveries?status=pending")
    assert resp.status_code == 200
    assert resp.json()[0]["auction_id"] == "auc-1"


def test_boat_owner_list_bidding_requests_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.bidding_service,
        "list_bidding_requests_for_owner",
        lambda **_kwargs: [_bidding_request_dict("br-1", status="pending")],
    )

    resp = client.get(f"{settings.API_V1_STR}/boat-owners/bidding-requests")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["total"] == 1
    assert body["bidding_requests"][0]["id"] == "br-1"


def test_boat_owner_respond_to_bidding_request_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.bidding_service,
        "respond_to_bidding_request",
        lambda **_kwargs: (None, "Not found"),
    )

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/bidding-requests/br-1",
        json={"status": "approved"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not found"


def test_boat_owner_respond_to_bidding_request_already_409(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.bidding_service,
        "respond_to_bidding_request",
        lambda **_kwargs: (None, "Already approved"),
    )

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/bidding-requests/br-1",
        json={"status": "approved"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Already approved"


def test_boat_owner_respond_to_bidding_request_other_error_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.bidding_service,
        "respond_to_bidding_request",
        lambda **_kwargs: (None, "Bad request"),
    )

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/bidding-requests/br-1",
        json={"status": "approved"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Bad request"


def test_boat_owner_respond_to_bidding_request_success_creates_notification(client, monkeypatch):
    client.app.dependency_overrides[deps.get_boat_owner_user] = _as_boat_owner

    monkeypatch.setattr(
        boat_owner_endpoints.bidding_service,
        "respond_to_bidding_request",
        lambda **_kwargs: (
            {
                **_bidding_request_dict("br-1", status="approved"),
            },
            None,
        ),
    )

    created = {}

    def fake_create_notification(**kwargs):
        created.update(kwargs)
        return {"id": "n-1"}

    monkeypatch.setattr(boat_owner_endpoints.notification_service, "create_notification", fake_create_notification)

    resp = client.put(
        f"{settings.API_V1_STR}/boat-owners/bidding-requests/br-1",
        json={"status": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert created["recipient_role"] == "agent"
    assert created["metadata"]["bidding_request_id"] == "br-1"
