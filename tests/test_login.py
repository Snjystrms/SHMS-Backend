import requests
import json

BASE_URL = "http://localhost:8000"

def test_login_success():
    print("\nTesting login success...")
    # These credentials come from 20260209_02_add_default_admin.py
    data = {
        "username": "admin@example.com",
        "password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/login", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        token = response.json().get("access_token")
        test_me_endpoint(token)
    else:
        print("Login failed, skipping /me test.")

def test_login_failure():
    print("\nTesting login failure (wrong password)...")
    data = {
        "username": "admin@example.com",
        "password": "wrongpassword"
    }
    response = requests.post(f"{BASE_URL}/login", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_me_endpoint(token):
    print("\nTesting /me endpoint with token...")
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(f"{BASE_URL}/me", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    try:
        test_login_success()
        test_login_failure()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure it's running on http://localhost:8000")
