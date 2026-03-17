import os
import sys
import uuid

import requests

# Allow importing app when running test as script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/api/v1")


def _login_officer() -> dict:
    login_data = {
        "mobile_number": "officer@example.com",
        "password": "officer123",
    }
    response = requests.post(f"{BASE_URL}/login", data=login_data)
    response.raise_for_status()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_arrival_completion_flow():
    """
    Flow:
    - create pending boat
    - log departure (temporary_departure)
    - attach inventory (departure)
    - log arrival (temporary_arrival)
    - run arrival inventory check with matching values (should finalize to arrival)
    - verify trip-status is arrived (not temporary_arrived)
    """

    headers = _login_officer()

    # 1) Create a pending boat (so we don't depend on existing DB boats)
    boat_number = f"TEST-{uuid.uuid4().hex[:6].upper()}"
    pending_boat_data = {
        "boat_number": boat_number,
        "mobile_number": "9999999999",
    }
    resp = requests.post(
        f"{BASE_URL}/port-officer/boats/pending-register",
        json=pending_boat_data,
        headers=headers,
    )
    resp.raise_for_status()
    boat_id = resp.json()["boat_id"]

    # 2) Log departure (stored as temporary_departure)
    resp = requests.post(
        f"{BASE_URL}/port-officer/boats/{boat_id}/movements",
        json={"movement_type": "departure"},
        headers=headers,
    )
    resp.raise_for_status()
    movement_id = resp.json()["id"]
    assert resp.json()["movement_type"] in ("temporary_departure", "departure")

    # 3) Attach inventory (marks movement_type to departure)
    dep_inventory = {
        "diesel_liters": 10.0,
        "ice_blocks": 2,
        "fishing_net_count": 5,
        "plastic_bottle_count": 3,
        "plastic_bag_count": 4,
    }
    resp = requests.post(
        f"{BASE_URL}/port-officer/movements/{movement_id}/inventory",
        json=dep_inventory,
        headers=headers,
    )
    resp.raise_for_status()

    # 4) Log arrival (stored as temporary_arrival)
    resp = requests.post(
        f"{BASE_URL}/port-officer/boats/{boat_id}/movements",
        json={"movement_type": "arrival"},
        headers=headers,
    )
    resp.raise_for_status()
    assert resp.json()["id"] == movement_id
    assert resp.json()["movement_type"] == "temporary_arrival"

    # 5) Arrival inventory check with matching values should finalize to arrival
    resp = requests.post(
        f"{BASE_URL}/port-officer/movements/{movement_id}/arrival/inventory/check",
        json=dep_inventory,
        headers=headers,
    )
    resp.raise_for_status()
    body = resp.json()
    assert body["all_matched"] is True

    # 6) Verify trip status shows arrived, not temporary_arrived
    resp = requests.get(
        f"{BASE_URL}/port-officer/boats/{boat_id}/trip-status",
        headers=headers,
    )
    resp.raise_for_status()
    status_body = resp.json()
    assert status_body["trip_status"] == "arrived"
    assert status_body["movement_type"] == "arrival"


if __name__ == "__main__":
    test_arrival_completion_flow()
    print("✅ Arrival completion flow passed.")

