import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"


def test_officer_crud():
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

    # 2. Create a Test Officer
    print("\n2. Creating a test officer...")
    officer_email = f"test_officer_{uuid.uuid4().hex[:6]}@example.com"
    officer_data = {
        "name": "Test Officer",
        "email": officer_email,
        "phone": "1234567890",
        "password": "password123"
    }
    response = requests.post(
        f"{BASE_URL}/admin/officers", 
        json=officer_data, 
        headers=headers
    )
    if response.status_code != 201:
        print(f"❌ Failed to create officer: {response.text}")
        return
    
    officer_id = response.json()["user_id"]
    print(f"✅ Officer created with ID: {officer_id}")

    # 3. List all officers
    print("\n3. Listing all officers...")
    response = requests.get(f"{BASE_URL}/admin/officers", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to list officers: {response.text}")
        return
    
    officers = response.json()["officers"]
    found = any(o["id"] == officer_id for o in officers)
    # Ensure the new registered_crew_count field is present in list response
    if found:
        officer_in_list = next(o for o in officers if o["id"] == officer_id)
        if "registered_crew_count" in officer_in_list:
            print(f"✅ Officer {officer_id} has registered_crew_count field: {officer_in_list['registered_crew_count']}")
        else:
            print(f"❌ Officer {officer_id} is missing registered_crew_count field")
            return
    if found:
        print(f"✅ Officer {officer_id} found in list")
    else:
        print(f"❌ Officer {officer_id} NOT found in list")
        return

    # 4. Get specific officer details
    print(f"\n4. Getting details for officer {officer_id}...")
    response = requests.get(f"{BASE_URL}/admin/officers/{officer_id}", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to get officer: {response.text}")
        return
    
    officer = response.json()["officer"]
    print(f"✅ Retrieved officer: {officer['name']} ({officer['email']})")

    # 5. Update officer details
    print(f"\n5. Updating officer {officer_id}...")
    update_data = {
        "name": "Updated Officer Name",
        "phone": "0987654321"
    }
    response = requests.put(
        f"{BASE_URL}/admin/officers/{officer_id}", 
        json=update_data, 
        headers=headers
    )
    if response.status_code != 200:
        print(f"❌ Failed to update officer: {response.text}")
        return
    
    # Verify update
    response = requests.get(f"{BASE_URL}/admin/officers/{officer_id}", headers=headers)
    updated_officer = response.json()["officer"]
    if updated_officer["name"] == "Updated Officer Name" and updated_officer["phone"] == "0987654321":
        print("✅ Officer updated successfully")
    else:
        print(f"❌ Officer update verification failed: {updated_officer}")

    # 6. Delete officer
    print(f"\n6. Deleting officer {officer_id}...")
    response = requests.delete(f"{BASE_URL}/admin/officers/{officer_id}", headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to delete officer: {response.text}")
        return
    print("✅ Officer deleted successfully")

    # 7. Verify deletion (not in list)
    print("\n7. Verifying deletion...")
    response = requests.get(f"{BASE_URL}/admin/officers", headers=headers)
    officers = response.json()["officers"]
    found = any(o["id"] == officer_id for o in officers)
    if not found:
        print("✅ Deletion verified: Officer no longer in list")
    else:
        print("❌ Deletion failed: Officer still in list")

    # 8. Try to get deleted officer
    print("\n8. Trying to get deleted officer details...")
    response = requests.get(f"{BASE_URL}/admin/officers/{officer_id}", headers=headers)
    if response.status_code == 404:
        print("✅ Correct: Get deleted officer returned 404")
    else:
        print(f"❌ Unexpected status code: {response.status_code}")

if __name__ == "__main__":
    test_officer_crud()
