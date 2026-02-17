import os
import sys
import requests
import json

# Allow importing app when running test as script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

BASE_URL = "http://localhost:8000/api/v1"


def _get_otp_for_phone(phone: str) -> str | None:
    """Test helper: read latest OTP for phone from DB."""
    try:
        from app.db.session import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT otp FROM password_reset_otps WHERE phone = %s ORDER BY created_at DESC LIMIT 1",
            (phone.strip(),),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def test_boat_owner_crud():
    # 1. Login as Admin
    print("\n1. Logging in as Admin...")
    login_data = {
        "mobile_number": "admin@example.com",
        "password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/login", data=login_data)
    if response.status_code != 200:
        print(f"❌ Admin login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Admin login successful")

    # 2. Register (saved to temp_users; OTP sent)
    print("\n2. Registering a test boat owner...")
    phone = "9876543210"
    boat_owner_data = {"name": "Test Boat Owner", "phone": phone}
    response = requests.post(f"{BASE_URL}/boat-owners/register", json=boat_owner_data)
    if response.status_code != 201:
        print(f"❌ Failed to register boat owner: {response.text}")
        return
    print("✅ Registration accepted; OTP sent")

    # 2b. Verify OTP to create user (user is created only after verify)
    otp = _get_otp_for_phone(phone)
    if not otp:
        print("❌ Could not get OTP from DB for verify step (run with app env)")
        return
    response = requests.post(
        f"{BASE_URL}/boat-owners/login/verify",
        json={"mobile_number": phone, "otp": otp},
    )
    if response.status_code != 200:
        print(f"❌ Failed to verify OTP: {response.text}")
        return
    boat_owner_id = response.json()["user"]["id"]
    print(f"✅ Boat owner verified and created with ID: {boat_owner_id}")

    # 3. List all boat owners
    print("\n3. Listing all boat owners...")
    response = requests.get(f"{BASE_URL}/admin/boat-owners", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to list boat owners: {response.text}")
        return
    
    boat_owners = response.json()["boat_owners"]
    found = any(bo["id"] == boat_owner_id for bo in boat_owners)
    if found:
        print(f"✅ Boat owner {boat_owner_id} found in list")
    else:
        print(f"❌ Boat owner {boat_owner_id} NOT found in list")
        return

    # 4. Get specific boat owner details
    print(f"\n4. Getting details for boat owner {boat_owner_id}...")
    response = requests.get(f"{BASE_URL}/admin/boat-owners/{boat_owner_id}", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to get boat owner: {response.text}")
        return
    
    boat_owner = response.json()["boat_owner"]
    print(f"✅ Retrieved boat owner: {boat_owner['name']} ({boat_owner['email']})")

    # 5. Update boat owner details
    print(f"\n5. Updating boat owner {boat_owner_id}...")
    update_data = {
        "name": "Updated Boat Owner Name",
        "phone": "1122334455"
    }
    response = requests.put(
        f"{BASE_URL}/admin/boat-owners/{boat_owner_id}", 
        json=update_data, 
        headers=headers
    )
    if response.status_code != 200:
        print(f"❌ Failed to update boat owner: {response.text}")
        return
    
    # Verify update
    response = requests.get(f"{BASE_URL}/admin/boat-owners/{boat_owner_id}", headers=headers)
    updated_boat_owner = response.json()["boat_owner"]
    if updated_boat_owner["name"] == "Updated Boat Owner Name" and updated_boat_owner["phone"] == "1122334455":
        print("✅ Boat owner updated successfully")
    else:
        print(f"❌ Boat owner update verification failed: {updated_boat_owner}")

    # 6. Delete boat owner
    print(f"\n6. Deleting boat owner {boat_owner_id}...")
    response = requests.delete(f"{BASE_URL}/admin/boat-owners/{boat_owner_id}", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to delete boat owner: {response.text}")
        return
    print("✅ Boat owner deleted successfully")

    # 7. Verify deletion (not in list)
    print("\n7. Verifying deletion...")
    response = requests.get(f"{BASE_URL}/admin/boat-owners", headers=headers)
    boat_owners = response.json()["boat_owners"]
    found = any(bo["id"] == boat_owner_id for bo in boat_owners)
    if not found:
        print("✅ Deletion verified: Boat owner no longer in list")
    else:
        print("❌ Deletion failed: Boat owner still in list")

    # 8. Try to get deleted boat owner
    print("\n8. Trying to get deleted boat owner details...")
    response = requests.get(f"{BASE_URL}/admin/boat-owners/{boat_owner_id}", headers=headers)
    if response.status_code == 404:
        print("✅ Correct: Get deleted boat owner returned 404")
    else:
        print(f"❌ Unexpected status code: {response.status_code}")

if __name__ == "__main__":
    test_boat_owner_crud()
