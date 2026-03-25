import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
 
from app.api import deps
from app.api.v1.endpoints import agents as agents_endpoints
from app.core.config import settings
 
 
def _as_agent():
    return {
        "id": "agent-1",
        "role": "agent",
        "name": "Agent",
        "phone": "9999999999",
        "email": "agent@example.com",
    }
 
 
@pytest.fixture
def client(request):
    """
    Minimal app for unit tests: mount ONLY the agents router.
    Avoid importing `app.main` which mounts all routers.
    """
    app = FastAPI()
    app.include_router(agents_endpoints.router, prefix=f"{settings.API_V1_STR}/agents")
    request.node._fastapi_app_under_test = app
    return TestClient(app)
 
 
def test_agents_register_success(client, monkeypatch):
    captured = {}
 
    def fake_start_temp_user_registration(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message": "OTP sent"}
 
    monkeypatch.setattr(agents_endpoints, "start_temp_user_registration", fake_start_temp_user_registration)
    monkeypatch.setattr(agents_endpoints.crud_user, "get_agent_by_phone", lambda _phone: None)
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/register",
        json={"name": "  Agent  ", "phone": " 9999999999 ", "aadhaar_number": None},
    )
 
    assert resp.status_code == 201
    assert resp.json() == {"success": True, "message": "OTP sent"}
    assert captured["name"] == "Agent"
    assert captured["phone"] == "9999999999"
    assert captured["duplicate_check"] is agents_endpoints.crud_user.get_agent_by_phone
 
 
def test_agents_register_duplicate_400(client, monkeypatch):
    def fake_start_temp_user_registration(**_kwargs):
        raise HTTPException(status_code=400, detail="An agent with this mobile number already exists")
 
    monkeypatch.setattr(agents_endpoints, "start_temp_user_registration", fake_start_temp_user_registration)
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/register",
        json={"name": "Agent", "phone": "9999999999"},
    )
 
    assert resp.status_code == 400
    assert resp.json()["detail"] == "An agent with this mobile number already exists"
 
 
def test_agents_login_send_otp_success(client, monkeypatch):
    def fake_send_otp_for_phone(phone, get_user_by_phone, not_found_detail):
        assert phone == "9999999999"
        assert get_user_by_phone is agents_endpoints.crud_user.get_agent_by_phone
        assert not_found_detail == agents_endpoints.AGENT_NOT_FOUND_DETAIL
        return {"masked_mobile": "******9999", "expires_in_minutes": 10}
 
    monkeypatch.setattr(agents_endpoints, "send_otp_for_phone", fake_send_otp_for_phone)
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/login/send-otp",
        json={"mobile_number": " 9999999999 "},
    )
 
    assert resp.status_code == 200
    assert resp.json() == {"masked_mobile": "******9999", "expires_in_minutes": 10}
 
 
def test_agents_login_send_otp_not_found_404(client, monkeypatch):
    def fake_send_otp_for_phone(_phone, _get_user_by_phone, _not_found_detail):
        raise HTTPException(status_code=404, detail=agents_endpoints.AGENT_NOT_FOUND_DETAIL)
 
    monkeypatch.setattr(agents_endpoints, "send_otp_for_phone", fake_send_otp_for_phone)
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/login/send-otp",
        json={"mobile_number": "9999999999"},
    )
 
    assert resp.status_code == 404
    assert resp.json()["detail"] == agents_endpoints.AGENT_NOT_FOUND_DETAIL
 
 
def test_agents_login_verify_success_returns_token_shape(client, monkeypatch):
    monkeypatch.setattr(
        agents_endpoints,
        "verify_otp_and_login_with_role",
        lambda **kwargs: {"id": "agent-1", "name": "Agent", "email": None, "role": "agent"},
    )
    monkeypatch.setattr(agents_endpoints.security, "create_access_token", lambda **_kwargs: "test.token.value")
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/login/verify",
        json={"mobile_number": "9999999999", "otp": "123456"},
    )
 
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "test.token.value"
    assert body["token_type"] == "bearer"
    assert body["user"] == {"id": "agent-1", "name": "Agent", "email": "", "role": "agent"}
 
 
def test_agents_dashboard_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    monkeypatch.setattr(
        agents_endpoints.trip_service,
        "get_agent_dashboard_arrivals",
        lambda agent_id: {
            "arrived_boats_count": 1,
            "arrived_boats": [
                {
                    "boat_id": "boat-1",
                    "boat_number": "MH-01-1234",
                    "boat_name": "B1",
                    "boat_status": "Arrived",
                    "time": "2026-01-01T00:00:00Z",
                    "bidding_request_status": None,
                }
            ],
        },
    )
 
    resp = client.get(f"{settings.API_V1_STR}/agents/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["id"] == "agent-1"
    assert body["arrived_boats_count"] == 1
    assert body["arrived_boats"][0]["boat_id"] == "boat-1"
 
 
def test_agents_send_bidding_request_success_sends_notification(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    result = {
        "id": "br-1",
        "boat_id": "boat-1",
        "boat_number": "MH-01-1234",
        "boat_name": "B1",
        "agent_id": "agent-1",
        "agent_name": "Agent",
        "status": "pending",
        "note": "hello",
        "created_at": "2026-01-01T00:00:00Z",
        "boat_owner_id": "bo-1",
    }
    monkeypatch.setattr(agents_endpoints.bidding_service, "create_bidding_request", lambda **_kwargs: (result, None))
 
    captured = {}
 
    def fake_create_notification(**kwargs):
        captured.update(kwargs)
        return "n-1"
 
    monkeypatch.setattr(agents_endpoints.notification_service, "create_notification", fake_create_notification)
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/bidding-request",
        json={"boat_id": "boat-1", "note": "hello"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["bidding_request"]["id"] == "br-1"
    assert "boat_owner_id" not in body["bidding_request"]
    assert captured["notification_type"] == "bidding_request"
    assert captured["recipient_role"] == "boat_owner"
 
 
@pytest.mark.parametrize(
    "err,expected_status",
    [
        ("Boat not found", 404),
        ("Already have a pending bidding request", 409),
        ("Your bidding request for this arrival was rejected", 409),
        ("Bad request", 400),
    ],
)
def test_agents_send_bidding_request_error_mapping(client, monkeypatch, err, expected_status):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
    monkeypatch.setattr(agents_endpoints.bidding_service, "create_bidding_request", lambda **_kwargs: (None, err))
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/bidding-request",
        json={"boat_id": "boat-1", "note": None},
    )
    assert resp.status_code == expected_status
 
 
def test_agents_list_my_bidding_requests_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    monkeypatch.setattr(
        agents_endpoints.bidding_service,
        "list_bidding_requests_for_agent",
        lambda agent_id, status_filter=None: [
            {
                "id": "br-1",
                "boat_id": "boat-1",
                "boat_number": "MH-01-1234",
                "boat_name": "B1",
                "agent_id": agent_id,
                "agent_name": "Agent",
                "status": status_filter or "pending",
                "note": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
    )
 
    resp = client.get(f"{settings.API_V1_STR}/agents/bidding-requests?status=pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["total"] == 1
    assert body["bidding_requests"][0]["id"] == "br-1"
 
 
def test_agents_list_deliveries_invalid_status_400(client):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    resp = client.get(f"{settings.API_V1_STR}/agents/deliveries?status=bad")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid status. Allowed values: pending, completed"
 
 
def test_agents_list_deliveries_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    items = [
        {
            "auction_id": "a-1",
            "auction_identifier": "A-1",
            "fish_type": "tuna",
            "auction_type": "english",
            "bid_price": 10.0,
            "requested_quantity": 5.0,
            "delivered_quantity": 0.0,
            "delivery_status": "pending",
            "delivered_at": None,
            "delivery_recorded_by": None,
            "start_time": "2026-01-01T00:00:00Z",
            "status": "pending",
        }
    ]
    monkeypatch.setattr(agents_endpoints.boat_owner_delivery_service, "get_deliveries_for_agent", lambda **_kwargs: items)
 
    resp = client.get(f"{settings.API_V1_STR}/agents/deliveries?status=pending")
    assert resp.status_code == 200
    assert resp.json() == items
 
 
def test_agents_initiate_delivery_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    detail = {
        "auction_id": "a-1",
        "buyer_name": "Buyer",
        "bid_price": 10.0,
        "auction_type": "english",
        "requested_quantity": 5.0,
        "delivered_quantity": 0.0,
        "delivery_status": "pending",
        "delivered_at": None,
        "delivery_recorded_by": None,
        "fish_type": "tuna",
        "start_time": "2026-01-01T00:00:00Z",
        "auction_identifier": "A-1",
        "is_already_delivered": False,
    }
    monkeypatch.setattr(
        agents_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction_by_agent",
        lambda **_kwargs: (detail, None),
    )
 
    resp = client.get(f"{settings.API_V1_STR}/agents/deliveries/initiate/a-1")
    assert resp.status_code == 200
    assert resp.json()["auction_id"] == "a-1"
 
 
def test_agents_initiate_delivery_no_winner_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    monkeypatch.setattr(
        agents_endpoints.boat_owner_delivery_service,
        "get_initiate_delivery_for_auction_by_agent",
        lambda **_kwargs: (None, "No winner found"),
    )
 
    resp = client.get(f"{settings.API_V1_STR}/agents/deliveries/initiate/a-1")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No winner found"
 
 
def test_agents_scan_delivery_missing_inputs_400(client):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    resp = client.post(f"{settings.API_V1_STR}/agents/deliveries/scan", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Provide auction_id and buyer_id, or qr_payload"
 
 
def test_agents_scan_delivery_invalid_qr_payload_json_400(client):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/deliveries/scan",
        json={"qr_payload": "{not-json}"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid qr_payload: expected JSON with auction_id and buyer_id"
 
 
def test_agents_scan_delivery_success_with_qr_payload(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    detail = {
        "auction_id": "a-1",
        "buyer_name": "Buyer",
        "bid_price": 10.0,
        "auction_type": "english",
        "requested_quantity": 5.0,
        "delivered_quantity": 0.0,
        "delivery_status": "pending",
        "delivered_at": None,
        "delivery_recorded_by": None,
        "fish_type": "tuna",
        "start_time": "2026-01-01T00:00:00Z",
        "auction_identifier": "A-1",
        "is_already_delivered": False,
    }
    monkeypatch.setattr(
        agents_endpoints.boat_owner_delivery_service,
        "get_delivery_by_qr_for_agent",
        lambda **_kwargs: (detail, None),
    )
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/deliveries/scan",
        json={"qr_payload": '{"auction_id":"a-1","buyer_id":"b-1"}'},
    )
    assert resp.status_code == 200
    assert resp.json()["auction_id"] == "a-1"
 
 
def test_agents_record_delivery_validation_422(client):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/deliveries/a-1/record",
        json={"delivered_quantity": 0},
    )
    assert resp.status_code == 422
 
 
def test_agents_record_delivery_service_error_400(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    monkeypatch.setattr(
        agents_endpoints.boat_owner_delivery_service,
        "record_delivery_by_agent",
        lambda **_kwargs: (None, "Something went wrong"),
    )
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/deliveries/a-1/record",
        json={"delivered_quantity": 1.0},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Something went wrong"
 
 
def test_agents_record_delivery_success_200(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    monkeypatch.setattr(
        agents_endpoints.boat_owner_delivery_service,
        "record_delivery_by_agent",
        lambda **_kwargs: ({"ok": True}, None),
    )
 
    resp = client.post(
        f"{settings.API_V1_STR}/agents/deliveries/a-1/record",
        json={"delivered_quantity": 1.0},
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Delivery recorded successfully"}
 
 
def test_agents_list_auctions_invalid_status_400(client):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    resp = client.get(f"{settings.API_V1_STR}/agents/auctions?status=bad")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid status. Allowed values: active, completed"
 
 
def test_agents_list_auctions_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_agent_user] = _as_agent
 
    items = [
        {
            "auction_id": "a-1",
            "auction_identifier": "A-1",
            "boat_name": "B1",
            "status": "active",
            "fish_type": "tuna",
            "bid_price": 10.0,
            "auction_type": "english",
            "start_time": "2026-01-01T00:00:00Z",
            "winner_name": None,
            "delivered_quantity": None,
        }
    ]
    monkeypatch.setattr(agents_endpoints.auction_service, "list_agent_auction_cards", lambda **_kwargs: items)
 
    resp = client.get(f"{settings.API_V1_STR}/agents/auctions?status=active")
    assert resp.status_code == 200
    assert resp.json() == items
