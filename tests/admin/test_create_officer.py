import requests
import json

BASE_URL = "http://localhost:8000"

def get_admin_token():
    print("Logging in as admin...")
    data = {
        "email_or_phone": "admin@example.com",
        "password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/login", data=data, timeout=10)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Login failed: {response.text}")
        return None

def test_create_officer_success(token):
    print("\nTesting officer creation (success)...")
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": "Officer Smith",
        "email": "smith@example.com",
        "phone": "1234567890",
        "password": "password123"
    }
    response = requests.post(f"{BASE_URL}/admin/create-officer", json=data, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_create_officer_duplicate(token):
    print("\nTesting officer creation (duplicate email)...")
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": "Officer Smith",
        "email": "smith@example.com",
        "phone": "1234567890",
        "password": "password123"
    }
    response = requests.post(f"{BASE_URL}/admin/create-officer", json=data, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_create_officer_unauthorized():
    print("\nTesting officer creation (unauthorized)...")
    data = {
        "name": "Unauthorized",
        "email": "unauthorized@example.com",
        "phone": "0000000000",
        "password": "password123"
    }
    response = requests.post(f"{BASE_URL}/admin/create-officer", json=data, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    token = get_admin_token()
    if token:
        test_create_officer_success(token)
        test_create_officer_duplicate(token)
        test_create_officer_unauthorized()
    else:
        print("Could not proceed with tests due to login failure.")
