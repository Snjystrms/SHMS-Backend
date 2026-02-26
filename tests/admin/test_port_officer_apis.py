import os
import sys
import uuid

import requests

# Allow importing app when running test as script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

BASE_URL = "http://localhost:8000/api/v1"


def _login_officer() -> dict:
    """Helper to log in as default officer and return auth headers."""
    print("\nLogging in as Officer...")
    login_data = {
        "mobile_number": "officer@example.com",
        "password": "officer123",
    }
    response = requests.post(f"{BASE_URL}/login", data=login_data)
    if response.status_code != 200:
        print(f"❌ Officer login failed: {response.status_code} {response.text}")
        return {}
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Officer login successful")
    return headers


def test_port_officer_apis():
    """
    Smoke-test all port officer APIs to verify they are reachable and return expected
    success or validation/error responses.
    """
    headers = _login_officer()
    if not headers:
        return

    # 1. Dashboard
    print("\n1. Fetching port officer dashboard...")
    response = requests.get(f"{BASE_URL}/port-officer/dashboard", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch dashboard: {response.status_code} {response.text}")
        return
    dashboard = response.json()
    if "user" in dashboard and "today_activity" in dashboard:
        print("✅ Dashboard fetched successfully with user and today_activity")
    else:
        print(f"❌ Dashboard response missing expected keys: {dashboard}")
        return

    # 2. Movement history (likely empty but should succeed)
    print("\n2. Fetching departure movement history (today)...")
    params = {"movement_type": "departure", "date_filter": "today"}
    response = requests.get(
        f"{BASE_URL}/port-officer/movements/history",
        headers=headers,
        params=params,
    )
    if response.status_code != 200:
        print(f"❌ Failed to fetch movement history: {response.status_code} {response.text}")
        return
    history = response.json()
    print(
        f"✅ Movement history fetched: "
        f"movement_type={history.get('movement_type')} "
        f"total_records={history.get('total_records')}"
    )

    # 3. Crew scanned history (likely empty but should succeed)
    print("\n3. Fetching crew scanned history (today)...")
    params = {"date_filter": "today"}
    response = requests.get(
        f"{BASE_URL}/port-officer/crew-scanned/history",
        headers=headers,
        params=params,
    )
    if response.status_code != 200:
        print(f"❌ Failed to fetch crew scanned history: {response.status_code} {response.text}")
        return
    crew_history = response.json()
    print(
        f"✅ Crew scanned history fetched: "
        f"date_filter={crew_history.get('date_filter')} "
        f"total_records={crew_history.get('total_records')}"
    )

    # 4. Register a pending boat (happy path)
    print("\n4. Creating pending boat registration...")
    pending_boat_data = {
        "boat_number": f"TEST-{uuid.uuid4().hex[:6].upper()}",
        "mobile_number": "9999999999",
    }
    response = requests.post(
        f"{BASE_URL}/port-officer/boats/pending-register",
        json=pending_boat_data,
        headers=headers,
    )
    if response.status_code != 201:
        print(f"❌ Failed to create pending boat: {response.status_code} {response.text}")
        return
    pending_boat = response.json()
    pending_boat_id = pending_boat.get("boat_id")
    print(f"✅ Pending boat created with ID: {pending_boat_id}")

    # 5. Identify unknown boat number (should return 404)
    print("\n5. Trying to identify an unknown boat (expect 404)...")
    unknown_boat_number = f"UNKNOWN-{uuid.uuid4().hex[:6].upper()}"
    response = requests.get(
        f"{BASE_URL}/port-officer/boats/identify/{unknown_boat_number}",
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: identify boat returned 404 for unknown boat number")
    else:
        print(
            f"❌ Unexpected status for unknown boat identify: "
            f"{response.status_code} {response.text}"
        )
        return

    # Use random UUIDs for non-existent boat/movement IDs
    fake_boat_id = str(uuid.uuid4())
    fake_movement_id = str(uuid.uuid4())

    # 6. Trip status for unknown boat (should return 404)
    print("\n6. Getting trip status for unknown boat (expect 404)...")
    response = requests.get(
        f"{BASE_URL}/port-officer/boats/{fake_boat_id}/trip-status",
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: trip status returned 404 for unknown boat")
    else:
        print(
            f"❌ Unexpected status for unknown boat trip status: "
            f"{response.status_code} {response.text}"
        )
        return

    # 7. Create boat movement for unknown boat (should surface 404)
    print("\n7. Creating boat movement for unknown boat (expect 404)...")
    movement_body = {"movement_type": "departure"}
    response = requests.post(
        f"{BASE_URL}/port-officer/boats/{fake_boat_id}/movements",
        json=movement_body,
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: create movement returned 404 for unknown boat")
    else:
        print(
            f"❌ Unexpected status for create movement on unknown boat: "
            f"{response.status_code} {response.text}"
        )
        return

    # 8. Attach crew list for unknown movement (should surface 404)
    print("\n8. Attaching crew to unknown movement (expect 404)...")
    crew_body = {
        "crew_members": [
            {"crew_member_id": str(uuid.uuid4())},
        ]
    }
    response = requests.post(
        f"{BASE_URL}/port-officer/movements/{fake_movement_id}/crew",
        json=crew_body,
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: attach crew returned 404 for unknown movement")
    else:
        print(
            f"❌ Unexpected status for attach crew on unknown movement: "
            f"{response.status_code} {response.text}"
        )
        return

    # 9. Attach inventory for unknown movement (should surface 404)
    print("\n9. Attaching inventory to unknown movement (expect 404)...")
    inventory_body = {
        "diesel_liters": 10.0,
        "ice_blocks": 1,
    }
    response = requests.post(
        f"{BASE_URL}/port-officer/movements/{fake_movement_id}/inventory",
        json=inventory_body,
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: attach inventory returned 404 for unknown movement")
    else:
        print(
            f"❌ Unexpected status for attach inventory on unknown movement: "
            f"{response.status_code} {response.text}"
        )
        return

    # 10. Get inventory for unknown movement (should surface 404)
    print("\n10. Fetching inventory for unknown movement (expect 404)...")
    response = requests.get(
        f"{BASE_URL}/port-officer/movements/{fake_movement_id}/inventory",
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: get inventory returned 404 for unknown movement")
    else:
        print(
            f"❌ Unexpected status for get inventory on unknown movement: "
            f"{response.status_code} {response.text}"
        )
        return

    # 11. Arrival crew scan without image/file (should surface 400)
    print("\n11. Calling arrival crew scan without image (expect 400)...")
    response = requests.post(
        f"{BASE_URL}/port-officer/movements/{fake_movement_id}/arrival/crew/scan",
        headers=headers,
    )
    if response.status_code == 400:
        print("✅ Correct: arrival crew scan returned 400 without image")
    else:
        print(
            f"❌ Unexpected status for arrival crew scan without image: "
            f"{response.status_code} {response.text}"
        )
        return

    # 12. Arrival inventory check for unknown movement (should surface 404)
    print("\n12. Calling arrival inventory check for unknown movement (expect 404)...")
    arrival_inventory_body = {
        "diesel_liters": 5.0,
        "ice_blocks": 0,
    }
    response = requests.post(
        f"{BASE_URL}/port-officer/movements/{fake_movement_id}/arrival/inventory/check",
        json=arrival_inventory_body,
        headers=headers,
    )
    if response.status_code == 404:
        print("✅ Correct: arrival inventory check returned 404 for unknown movement")
    else:
        print(
            f"❌ Unexpected status for arrival inventory check on unknown movement: "
            f"{response.status_code} {response.text}"
        )
        return

    print("\n🎉 All port officer API smoke tests completed.")


if __name__ == "__main__":
    test_port_officer_apis()

