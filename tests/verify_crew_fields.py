
import sys
import os
import numpy as np

# Add project root to python path
sys.path.append(os.getcwd())

from app.services import face_service

def test_crew_member_fields():
    print("Testing Crew Member Fields...")
    
    # Mock embedding
    embedding = np.random.rand(512).astype(np.float32)
    
    name = "Test Crew Member"
    aadhaar = "1234-5678-9012"
    contact = "9876543210"
    
    # 1. Register
    print(f"Registering user with aadhaar={aadhaar}, contact={contact}")
    user_id = face_service.register_user(
        name,
        embedding,
        aadhaar_number=aadhaar,
        emergency_contact_number=contact,
        registered_by_user_id=None,
    )
    
    if not user_id:
        print("FAILED: register_user returned None")
        return
        
    print(f"User registered with ID: {user_id}")
    
    # 2. Get by ID
    print("Fetching user by ID...")
    user_data = face_service.get_crew_member_by_id(user_id)
    
    if not user_data:
        print("FAILED: get_crew_member_by_id returned None")
        return
        
    print(f"Fetched Data: {user_data}")
    
    if user_data['aadhaar_number'] != aadhaar:
        print(f"FAILED: aadhaar_number mismatch. Expected {aadhaar}, got {user_data['aadhaar_number']}")
    if user_data['emergency_contact_number'] != contact:
        print(f"FAILED: emergency_contact_number mismatch. Expected {contact}, got {user_data['emergency_contact_number']}")
        
    # 3. Update
    new_aadhaar = "9999-9999-9999"
    print(f"Updating user aadhaar to {new_aadhaar}...")
    success = face_service.update_crew_member(user_id, aadhaar_number=new_aadhaar)
    
    if not success:
        print("FAILED: update_crew_member returned False")
    
    # 4. Verify Update
    user_data = face_service.get_crew_member_by_id(user_id)
    print(f"Fetched Data after update: {user_data}")
    
    if user_data['aadhaar_number'] != new_aadhaar:
        print(f"FAILED: aadhaar_number update failed. Expected {new_aadhaar}, got {user_data['aadhaar_number']}")
        
    # 5. Cleanup
    print("Deleting test user...")
    face_service.delete_crew_member(user_id)
    
    print("SUCCESS: All tests passed!")

if __name__ == "__main__":
    test_crew_member_fields()
