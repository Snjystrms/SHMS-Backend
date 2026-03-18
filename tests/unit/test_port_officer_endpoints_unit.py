import sys
import types

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.services import notification_service, trip_service, user_service


def _import_port_officer_endpoints_safely():
    """
    `app/api/v1/endpoints/port_officer.py` imports face/ocr services that pull in
    heavy native deps (cv2/numpy) which can crash Python on some macOS setups.

    For unit tests we stub those modules before importing the router module.
    """
    # Stub out heavy modules before import to avoid importing cv2/numpy.
    if "app.services.face_service" not in sys.modules:
        face_stub = types.ModuleType("app.services.face_service")
        face_stub.identify_faces_in_image = lambda _image_bytes: {"faces": []}
        face_stub.draw_face_boxes_on_image = lambda _image_bytes, _faces: None
        sys.modules["app.services.face_service"] = face_stub

    if "app.services.boat_scan_service" not in sys.modules:
        scan_stub = types.ModuleType("app.services.boat_scan_service")
        scan_stub.scan_boat_number = lambda _image_bytes: {"boat_number": None, "confidence": None, "all_detected_text": []}
        sys.modules["app.services.boat_scan_service"] = scan_stub

    from app.api.v1.endpoints import port_officer as port_officer_endpoints  # noqa: WPS433

    return port_officer_endpoints


def _as_officer():
    return {"id": "off-1", "role": "officer", "name": "Officer"}


@pytest.fixture
def client(request):
    """
    Minimal app for unit tests: mount ONLY the port-officer router.
    Avoids importing the full app (which imports numpy-heavy routers).
    """
    port_officer_endpoints = _import_port_officer_endpoints_safely()
    app = FastAPI()
    app.include_router(
        port_officer_endpoints.router,
        prefix=f"{settings.API_V1_STR}/port-officer",
    )
    request.node._fastapi_app_under_test = app
    return TestClient(app)


def test_port_officer_dashboard_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(
        trip_service,
        "get_dashboard_today_counts",
        lambda: {
            "departures": 1,
            "arrivals": 2,
            "crew_registration": 3,
            "crew_verification": 4,
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/port-officer/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["id"] == "off-1"
    assert body["today_activity"]["departures"] == 1
    assert body["today_activity"]["arrivals"] == 2


def test_port_officer_identify_boat_blank_number_400(client):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    resp = client.post(f"{settings.API_V1_STR}/port-officer/boats/identify/   ")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Boat number is required"


def test_port_officer_identify_boat_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(user_service, "get_boat_by_number_with_owner", lambda _n: None)
    monkeypatch.setattr(user_service, "get_boat_by_number", lambda _n: None)

    resp = client.post(f"{settings.API_V1_STR}/port-officer/boats/identify/MH-01-1234")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat not found"


def test_port_officer_trip_status_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(trip_service, "get_boat_trip_status", lambda _boat_id: None)

    resp = client.get(f"{settings.API_V1_STR}/port-officer/boats/boat-404/trip-status")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Boat not found"


def test_port_officer_movement_history_page_validation_400(client):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    resp = client.get(
        f"{settings.API_V1_STR}/port-officer/movements/history?movement_type=departure&page=0"
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "page must be >= 1"


def test_port_officer_crew_scanned_history_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

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
        f"{settings.API_V1_STR}/port-officer/crew-scanned/history?date_filter=today&page=1&page_size=10"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["date_filter"] == "today"
    assert body["total_records"] == 1
    assert body["records"][0]["crew_id"] == "c-1"


def test_port_officer_pending_register_validation_400(client):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/boats/pending-register",
        json={"boat_number": "", "mobile_number": ""},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Boat number is required"


def test_port_officer_pending_register_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(user_service, "create_pending_boat", lambda boat_number, mobile_number: "boat-1")

    sent = {}

    class _SMS:
        def send_message(self, mobile_number, message):
            sent["mobile_number"] = mobile_number
            sent["message"] = message

    port_officer_endpoints = _import_port_officer_endpoints_safely()
    monkeypatch.setattr(port_officer_endpoints, "_get_sms", lambda: _SMS())
    monkeypatch.setattr(notification_service, "create_notification", lambda **kwargs: "n-1")

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/boats/pending-register",
        json={"boat_number": "MH-01-1234", "mobile_number": "9999999999"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["boat_id"] == "boat-1"
    assert sent["mobile_number"] == "9999999999"


def test_port_officer_scan_number_missing_file_422(client):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    # FastAPI validation for required UploadFile => 422
    resp = client.post(f"{settings.API_V1_STR}/port-officer/boats/scan-number")
    assert resp.status_code == 422


def test_port_officer_scan_number_empty_file_400(client):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/boats/scan-number",
        files={"file": ("boat.png", b"", "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Uploaded file is empty"


def test_port_officer_scan_number_success_boat_found(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    port_officer_endpoints = _import_port_officer_endpoints_safely()

    monkeypatch.setattr(
        port_officer_endpoints.boat_scan_service,
        "scan_boat_number",
        lambda _image_bytes: {"boat_number": "MH-01-1234", "confidence": 0.9, "all_detected_text": ["MH", "01", "1234"]},
    )
    monkeypatch.setattr(
        user_service,
        "get_boat_by_number_with_owner",
        lambda _n: {
            "id": "boat-1",
            "boat_number": "MH-01-1234",
            "boat_name": "B1",
            "owner_name": "Owner",
            "harbor_name": "Mumbai",
            "boat_type": "Trawler",
        },
    )
    monkeypatch.setattr(trip_service, "get_boat_trip_status", lambda _boat_id: None)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/boats/scan-number",
        files={"file": ("boat.png", b"fakeimg", "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["boat_number"] == "MH-01-1234"
    assert body["boat"]["boat_id"] == "boat-1"
    assert body["boat"]["is_pending_registration"] is False


def test_port_officer_create_boat_movement_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    movement_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        trip_service,
        "create_boat_movement",
        lambda **kwargs: (
            {
                "id": "m-1",
                "boat_id": kwargs["boat_id"],
                "movement_type": "departure",
                "movement_at": movement_at,
                "partial_arrival_reason": None,
                "partial_arrival_details": None,
                "image_url": None,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        user_service,
        "get_boat_by_id",
        lambda _id: {"id": _id, "boat_number": "MH-01-1234", "boat_name": "B1", "boat_owner_id": "bo-1"},
    )

    created = {"count": 0}

    def fake_create_notification(**_kwargs):
        created["count"] += 1
        return "n-1"

    monkeypatch.setattr(notification_service, "create_notification", fake_create_notification)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/boats/boat-1/movements",
        json={"movement_type": "departure"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "m-1"
    assert body["boat_id"] == "boat-1"
    assert body["movement_type"] == "departure"
    # Admin + boat owner notifications
    assert created["count"] == 2


def test_port_officer_set_movement_crew_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(
        trip_service,
        "set_boat_movement_crew",
        lambda **kwargs: (
            {
                "movement_id": kwargs["movement_id"],
                "boat_id": "boat-1",
                "total_crew_count": len(kwargs["crew_member_ids"]),
                "identified_crew_ids": kwargs["crew_member_ids"],
                "unidentified_count": kwargs.get("unidentified_count") or 0,
                "success": True,
                "message": "Crew members added successfully.",
            },
            None,
        ),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/movements/m-1/crew",
        json={"crew_members": [{"crew_member_id": "c-1"}, {"crew_member_id": "c-2", "crop_id": "crop-2"}]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["movement_id"] == "m-1"
    assert body["total_crew_count"] == 2


def test_port_officer_set_movement_inventory_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(
        trip_service,
        "set_boat_movement_inventory",
        lambda **kwargs: (
            {
                "movement_id": kwargs["movement_id"],
                "boat_id": "boat-1",
                "diesel_liters": kwargs.get("diesel_liters"),
                "ice_blocks": kwargs.get("ice_blocks"),
                "fishing_net_count": kwargs.get("fishing_net_count"),
                "plastic_bottle_count": kwargs.get("plastic_bottle_count"),
                "plastic_bag_count": kwargs.get("plastic_bag_count"),
                "success": True,
                "message": "Inventory added successfully.",
            },
            None,
        ),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/movements/m-1/inventory",
        json={"diesel_liters": 10.5, "ice_blocks": 2},
    )
    assert resp.status_code == 201
    assert resp.json()["movement_id"] == "m-1"


def test_port_officer_get_movement_inventory_success(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(trip_service, "get_trip_movement_by_id", lambda _id: {"boat_id": "boat-1"})
    monkeypatch.setattr(trip_service, "get_departure_inventory", lambda _id: {"diesel_liters": 10.0, "ice_blocks": 1})

    resp = client.get(f"{settings.API_V1_STR}/port-officer/movements/m-1/inventory")
    assert resp.status_code == 200
    body = resp.json()
    assert body["movement_id"] == "m-1"
    assert body["boat_id"] == "boat-1"
    assert body["diesel_liters"] == pytest.approx(10.0)


def test_port_officer_arrival_crew_scan_missing_inputs_400(client):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    resp = client.post(f"{settings.API_V1_STR}/port-officer/movements/m-1/arrival/crew/scan")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Provide either an image file upload or image_url"


def test_port_officer_arrival_inventory_check_movement_not_found_404(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(trip_service, "get_trip_movement_by_id", lambda _id: None)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/movements/m-404/arrival/inventory/check",
        json={"diesel_liters": 1.0},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Movement not found or not a valid trip (departure/arrival)."


def test_port_officer_arrival_inventory_check_success_marks_complete(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(trip_service, "get_trip_movement_by_id", lambda _id: {"boat_id": "boat-1"})
    monkeypatch.setattr(
        trip_service,
        "get_departure_inventory",
        lambda _id: {
            "diesel_liters": 10.0,
            "ice_blocks": 2,
            "fishing_net_count": 1,
            "plastic_bottle_count": 1,
            "plastic_bag_count": 1,
        },
    )

    called = {"done": False}
    monkeypatch.setattr(
        trip_service,
        "update_movement_to_complete_arrival",
        lambda _id: called.__setitem__("done", True),
    )

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/movements/m-1/arrival/inventory/check",
        json={
            "diesel_liters": 10.0,
            "ice_blocks": 2,
            "fishing_net_count": 1,
            "plastic_bottle_count": 1,
            "plastic_bag_count": 1,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["movement_id"] == "m-1"
    assert body["boat_id"] == "boat-1"
    assert called["done"] is True


def test_port_officer_forgot_password_calls_send_otp(client, monkeypatch):
    port_officer_endpoints = _import_port_officer_endpoints_safely()

    captured = {}

    def fake_send_otp_for_phone(mobile_number, duplicate_check, not_found_detail):
        captured["mobile_number"] = mobile_number
        captured["duplicate_check"] = duplicate_check
        captured["not_found_detail"] = not_found_detail
        return {"success": True}

    monkeypatch.setattr(port_officer_endpoints, "send_otp_for_phone", fake_send_otp_for_phone)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/forgot-password",
        json={"mobile_number": "9999999999"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    assert captured["mobile_number"] == "9999999999"
    assert captured["not_found_detail"] == "No port officer found with this mobile number"


def test_port_officer_verify_otp_officer_not_found_404(client, monkeypatch):
    monkeypatch.setattr(user_service, "get_officer_by_phone", lambda _phone: None)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/verify-otp",
        json={"mobile_number": "9999999999", "otp": "123456"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No port officer found with this mobile number"


def test_port_officer_verify_otp_invalid_otp_400(client, monkeypatch):
    monkeypatch.setattr(user_service, "get_officer_by_phone", lambda _phone: {"id": "off-1"})
    monkeypatch.setattr(user_service, "verify_otp", lambda _phone, _otp: False)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/verify-otp",
        json={"mobile_number": "9999999999", "otp": "bad"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired OTP"


def test_port_officer_verify_otp_success_returns_reset_token(client, monkeypatch):
    port_officer_endpoints = _import_port_officer_endpoints_safely()

    monkeypatch.setattr(user_service, "get_officer_by_phone", lambda _phone: {"id": "off-1"})
    monkeypatch.setattr(user_service, "verify_otp", lambda _phone, _otp: True)
    monkeypatch.setattr(
        port_officer_endpoints.security,
        "create_password_reset_token",
        lambda _user_id: "reset-token",
    )

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/verify-otp",
        json={"mobile_number": "9999999999", "otp": "123456"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["reset_token"] == "reset-token"


def test_port_officer_reset_password_mismatch_400(client):
    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/reset-password",
        json={"reset_token": "t", "new_password": "aaaaaa", "confirm_password": "bbbbbb"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Passwords do not match"


def test_port_officer_reset_password_invalid_token_400(client, monkeypatch):
    port_officer_endpoints = _import_port_officer_endpoints_safely()
    monkeypatch.setattr(port_officer_endpoints.security, "decode_password_reset_token", lambda _t: None)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/reset-password",
        json={"reset_token": "bad", "new_password": "aaaaaa", "confirm_password": "aaaaaa"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired reset token"


def test_port_officer_reset_password_success(client, monkeypatch):
    port_officer_endpoints = _import_port_officer_endpoints_safely()

    monkeypatch.setattr(port_officer_endpoints.security, "decode_password_reset_token", lambda _t: "off-1")
    monkeypatch.setattr(user_service, "get_user_by_id", lambda _id: {"id": _id, "role": "officer"})
    monkeypatch.setattr(port_officer_endpoints.security, "get_password_hash", lambda _pw: "hashed")
    monkeypatch.setattr(user_service, "update_user_password", lambda _id, _hashed: True)

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/reset-password",
        json={"reset_token": "t", "new_password": "aaaaaa", "confirm_password": "aaaaaa"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password reset successfully"


def test_port_officer_identify_boat_success_formats_last_departure(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(
        user_service,
        "get_boat_by_number_with_owner",
        lambda _n: {
            "id": "boat-1",
            "boat_number": "MH-01-1234",
            "boat_name": "B1",
            "owner_name": "Owner",
            "harbor_name": "Mumbai",
            "boat_type": "Trawler",
        },
    )
    monkeypatch.setattr(
        trip_service,
        "get_boat_trip_status",
        lambda _boat_id: {
            "boat_id": "boat-1",
            "boat_number": "MH-01-1234",
            "trip_status": "sailing",
            "movement_type": "departure",
            "departure_details": {
                "departure_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "from_port": "Mumbai",
                "status_label": "Sailing",
            },
        },
    )

    resp = client.post(f"{settings.API_V1_STR}/port-officer/boats/identify/MH-01-1234")
    assert resp.status_code == 200
    body = resp.json()
    assert body["registration_no"] == "MH-01-1234"
    assert body["boat_id"] == "boat-1"
    assert body["is_pending_registration"] is False
    assert body["last_logged_departure"] is not None


def test_port_officer_trip_status_success_resolves_image_urls(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(
        trip_service,
        "get_boat_trip_status",
        lambda _boat_id: {
            "boat_id": _boat_id,
            "boat_number": "MH-01-1234",
            "trip_status": "sailing",
            "movement_type": "departure",
            "departure_details": {
                "departure_at": "2026-01-01T00:00:00Z",
                "from_port": "Mumbai",
                "image_url": "/uploads/dep.png",
            },
            "last_movement_image_url": "/uploads/last.png",
        },
    )

    resp = client.get(f"{settings.API_V1_STR}/port-officer/boats/boat-1/trip-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["departure_details"]["image_url"].startswith("http")
    assert body["last_movement_image_url"].startswith("http")


def test_port_officer_movement_history_success_resolves_image_url(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(
        trip_service,
        "get_movement_history",
        lambda **kwargs: [
            {
                "movement_id": "m-1",
                "boat_id": "boat-1",
                "boat_number": "MH-01-1234",
                "boat_name": "B1",
                "movement_at": "2026-01-01T00:00:00Z",
                "image_url": "/uploads/m.png",
            }
        ],
    )

    resp = client.get(
        f"{settings.API_V1_STR}/port-officer/movements/history?movement_type=departure&date_filter=today&page=1&page_size=10"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_records"] == 1
    assert body["records"][0]["movement_id"] == "m-1"
    # BoatMovementHistoryItem schema doesn't expose image_url; response intentionally omits it.
    assert "image_url" not in body["records"][0]


def test_port_officer_arrival_crew_scan_success_with_departure_crew(client, monkeypatch):
    client.app.dependency_overrides[deps.get_admin_or_officer_user] = _as_officer

    monkeypatch.setattr(trip_service, "get_trip_movement_by_id", lambda _id: {"boat_id": "boat-1"})
    monkeypatch.setattr(
        trip_service,
        "get_departure_crew_with_details",
        lambda _id: [{"id": "c-1", "name": "Crew 1", "is_pilot": False}],
    )

    resp = client.post(
        f"{settings.API_V1_STR}/port-officer/movements/m-1/arrival/crew/scan",
        files={"file": ("arr.png", b"fakeimg", "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["movement_id"] == "m-1"
    assert body["boat_id"] == "boat-1"
    assert body["crew_at_departure"] == 1
    assert body["missing_crew_count"] == 1

