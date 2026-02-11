import requests
import json
import random
import string

BASE_URL = "http://127.0.0.1:8007/api/v1"  # Adjusted based on running terminals (assuming port 8007)

def get_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def test_registration():
    random_id = get_random_string(6)
    email = f"boat_owner_{random_id}@example.com"
    phone = f"9{random.randint(100000000, 999999999)}"
    name = f"Boat Owner {random_id}"
    password = "securepassword123"

    payload = {
        "name": name,
        "email": email,
        "phone": phone,
        "password": password
    }

    print(f"1. Registering new boat owner: {email}...")
    response = requests.post(f"{BASE_URL}/register", json=payload)
    
    if response.status_code == 201:
        print("✅ Registration successful")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        user_id = response.json().get("user_id")
    else:
        print(f"❌ Registration failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return

    print("\n2. Testing duplicate registration (same email)...")
    duplicate_payload = payload.copy()
    duplicate_payload["phone"] = f"8{random.randint(100000000, 999999999)}"
    response = requests.post(f"{BASE_URL}/register", json=duplicate_payload)
    if response.status_code == 400:
        print("✅ Duplicate email correctly blocked")
    else:
        print(f"❌ Duplicate email test failed with status {response.status_code}")

    print("\n3. Testing login with new credentials...")
    login_payload = {
        "mobile_number": email,
        "password": password
    }
    # Note: The login endpoint uses Form data, not JSON
    response = requests.post(f"{BASE_URL}/login", data=login_payload)
    if response.status_code == 200:
        print("✅ Login successful")
        user_data = response.json().get("user", {})
        print(f"User Role: {user_data.get('role')}")
        if user_data.get("role") == "boat_owner":
            print("✅ Correct role assigned")
        else:
            print(f"❌ Incorrect role assigned: {user_data.get('role')}")
    else:
        print(f"❌ Login failed with status {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    test_registration()
