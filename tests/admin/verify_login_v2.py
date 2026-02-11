import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_login(identifier, password, label):
    print(f"\nTesting {label} login...")
    data = {
        "email_or_phone": identifier,
        "password": password
    }
    try:
        response = requests.post(f"{BASE_URL}/login", data=data)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ {label} login successful")
            # print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ {label} login failed")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with admin email (known from tests/test_login.py)
    test_login("admin@example.com", "admin123", "Email")
    test_login("0000000000", "admin123", "Phone")
    # We need a phone number to test. 
    # Let's try to test with a phone number if we can find one.
