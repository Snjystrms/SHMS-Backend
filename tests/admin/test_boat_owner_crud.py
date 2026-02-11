import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"


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

    # 2. Register a Test Boat Owner
    print("\n2. Registering a test boat owner...")
    boat_owner_email = f"test_boat_owner_{uuid.uuid4().hex[:6]}@example.com"
    boat_owner_data = {
        "name": "Test Boat Owner",
        "email": boat_owner_email,
        "phone": "9876543210",
        "password": "password123"
    }
    response = requests.post(
        f"{BASE_URL}/boat-owners/register", 
        json=boat_owner_data
    )
    if response.status_code != 201:
        print(f"❌ Failed to register boat owner: {response.text}")
        return
    
    boat_owner_id = response.json()["user_id"]
    print(f"✅ Boat owner registered with ID: {boat_owner_id}")

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
