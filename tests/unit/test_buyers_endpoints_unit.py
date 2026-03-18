import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1.endpoints import buyers as buyers_endpoints
from app.core.config import settings


def _as_buyer():
    return {
        "id": "buyer-1",
        "role": "buyer",
        "name": "Buyer",
        "phone": "9999999999",
        "email": "buyer@example.com",
    }


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
    Minimal app for unit tests: mount ONLY the buyers router.
    Avoid importing `app.main` which mounts all routers.
    """
    app = FastAPI()
    app.include_router(buyers_endpoints.router, prefix=f"{settings.API_V1_STR}/buyers")
    request.node._fastapi_app_under_test = app
    return TestClient(app)


def test_buyers_dashboard_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_buyer_user] = _as_buyer

    monkeypatch.setattr(
        buyers_endpoints.buyer_dashboard_service,
        "get_buyer_dashboard",
        lambda buyer_id: {
            "total_bids": 2,
            "pending_delivery": 1,
            "live_auctions": [
                {
                    "auction_id": "a-1",
                    "auction_identifier": "A-1",
                    "item_title": "Lot 1",
                    "status": "active",
                    "fish_type": "tuna",
                    "current_bid_price": 10.0,
                    "auction_type": "english",
                    "start_time": "2026-01-01T00:00:00Z",
                    "my_bid": 9.0,
                    "required_quantity": "5",
                }
            ],
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/buyers/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"] == {"id": "buyer-1", "name": "Buyer"}
    assert body["total_bids"] == 2
    assert body["pending_delivery"] == 1
    assert body["live_auctions"][0]["auction_id"] == "a-1"


def test_buyers_dashboard_forbidden_for_non_buyer(client):
    client.app.dependency_overrides[deps.get_current_user] = _as_agent

    resp = client.get(f"{settings.API_V1_STR}/buyers/dashboard")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Buyer access required"


def test_buyers_list_deliveries_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_current_user] = _as_buyer

    deliveries = [
        {
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
    ]
    monkeypatch.setattr(buyers_endpoints.buyer_delivery_service, "list_deliveries", lambda buyer_id: deliveries)

    resp = client.get(f"{settings.API_V1_STR}/buyers/deliveries")
    assert resp.status_code == 200
    assert resp.json() == {"deliveries": deliveries}


def test_buyers_delivery_detail_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_current_user] = _as_buyer

    detail = {
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
        "buyer_name": "Buyer",
        "qr_payload": '{"auction_id":"a-1","buyer_id":"buyer-1"}',
    }
    monkeypatch.setattr(
        buyers_endpoints.buyer_delivery_service,
        "get_delivery_detail",
        lambda delivery_id, buyer_id: detail,
    )

    resp = client.get(f"{settings.API_V1_STR}/buyers/deliveries/d-1")
    assert resp.status_code == 200
    assert resp.json()["delivery_id"] == "d-1"
    assert resp.json()["buyer_name"] == "Buyer"


def test_buyers_delivery_detail_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_current_user] = _as_buyer

    monkeypatch.setattr(
        buyers_endpoints.buyer_delivery_service,
        "get_delivery_detail",
        lambda delivery_id, buyer_id: None,
    )

    resp = client.get(f"{settings.API_V1_STR}/buyers/deliveries/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Delivery not found"


def test_buyers_auction_history_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_buyer_user] = _as_buyer

    auctions = [
        {
            "auction_id": "a-1",
            "auction_identifier": "A-1",
            "description": "Lot 1",
            "status": "Bid Won",
            "fish_type": "tuna",
            "bid_price": 10.0,
            "auction_type": "english",
            "start_time": "2026-01-01T00:00:00Z",
            "my_bid": 10.0,
            "required_quantity": 5.0,
        }
    ]
    monkeypatch.setattr(buyers_endpoints.buyer_history_service, "list_auction_history", lambda buyer_id: auctions)

    resp = client.get(f"{settings.API_V1_STR}/buyers/history/auctions")
    assert resp.status_code == 200
    assert resp.json() == {"auctions": auctions}


def test_buyers_delivery_history_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_buyer_user] = _as_buyer

    deliveries = [
        {
            "delivery_id": "d-1",
            "auction_identifier": "A-1",
            "description": "Lot 1",
            "status": "Delivery Completed",
            "my_bid": 10.0,
            "required_quantity": 5.0,
            "delivered_quantity": 5.0,
            "delivery_status": "completed",
            "delivered_at": None,
        }
    ]
    monkeypatch.setattr(buyers_endpoints.buyer_history_service, "list_delivery_history", lambda buyer_id: deliveries)

    resp = client.get(f"{settings.API_V1_STR}/buyers/history/deliveries")
    assert resp.status_code == 200
    assert resp.json() == {"deliveries": deliveries}


def test_buyers_register_success(client, monkeypatch):
    captured = {}

    def fake_start_temp_user_registration(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message": "OTP sent"}

    monkeypatch.setattr(buyers_endpoints, "start_temp_user_registration", fake_start_temp_user_registration)
    monkeypatch.setattr(buyers_endpoints.crud_user, "get_buyer_by_phone", lambda _phone: None)

    resp = client.post(
        f"{settings.API_V1_STR}/buyers/register",
        json={"name": "  Buyer  ", "phone": " 9999999999 ", "aadhaar_number": None},
    )

    assert resp.status_code == 201
    assert resp.json() == {"success": True, "message": "OTP sent"}
    assert captured["name"] == "Buyer"
    assert captured["phone"] == "9999999999"
    assert captured["duplicate_check"] is buyers_endpoints.crud_user.get_buyer_by_phone
    assert captured["aadhaar_number"] is None


def test_buyers_register_duplicate_400(client, monkeypatch):
    def fake_start_temp_user_registration(**_kwargs):
        raise HTTPException(status_code=400, detail="A buyer with this mobile number already exists")

    monkeypatch.setattr(buyers_endpoints, "start_temp_user_registration", fake_start_temp_user_registration)

    resp = client.post(
        f"{settings.API_V1_STR}/buyers/register",
        json={"name": "Buyer", "phone": "9999999999"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "A buyer with this mobile number already exists"


def test_buyers_login_send_otp_success(client, monkeypatch):
    def fake_send_otp_for_phone(phone, get_user_by_phone, not_found_detail):
        assert phone == "9999999999"
        assert get_user_by_phone is buyers_endpoints.crud_user.get_buyer_by_phone
        assert not_found_detail == buyers_endpoints.BUYER_NOT_FOUND_DETAIL
        return {"masked_mobile": "******9999", "expires_in_minutes": 10}

    monkeypatch.setattr(buyers_endpoints, "send_otp_for_phone", fake_send_otp_for_phone)

    resp = client.post(
        f"{settings.API_V1_STR}/buyers/login/send-otp",
        json={"mobile_number": " 9999999999 "},
    )
    assert resp.status_code == 200
    assert resp.json() == {"masked_mobile": "******9999", "expires_in_minutes": 10}


def test_buyers_login_send_otp_not_found_404(client, monkeypatch):
    def fake_send_otp_for_phone(_phone, _get_user_by_phone, _not_found_detail):
        raise HTTPException(status_code=404, detail=buyers_endpoints.BUYER_NOT_FOUND_DETAIL)

    monkeypatch.setattr(buyers_endpoints, "send_otp_for_phone", fake_send_otp_for_phone)

    resp = client.post(
        f"{settings.API_V1_STR}/buyers/login/send-otp",
        json={"mobile_number": "9999999999"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == buyers_endpoints.BUYER_NOT_FOUND_DETAIL


def test_buyers_login_verify_success_returns_token_shape(client, monkeypatch):
    monkeypatch.setattr(
        buyers_endpoints,
        "verify_otp_and_login_with_role",
        lambda **kwargs: {"id": "buyer-1", "name": "Buyer", "email": None, "role": "buyer"},
    )
    monkeypatch.setattr(buyers_endpoints.security, "create_access_token", lambda **_kwargs: "test.token.value")

    resp = client.post(
        f"{settings.API_V1_STR}/buyers/login/verify",
        json={"mobile_number": "9999999999", "otp": "123456"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "test.token.value"
    assert body["token_type"] == "bearer"
    assert body["user"] == {"id": "buyer-1", "name": "Buyer", "email": "", "role": "buyer"}

