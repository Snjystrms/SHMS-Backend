import uuid
import numpy as np
import cv2
from insightface.app import FaceAnalysis
from app.db.session import get_db_connection
from app.core.config import settings


# Initialize FaceAnalysis once
face_app = FaceAnalysis(name="buffalo_l")
face_app.prepare(ctx_id=0)

# Removed hardcoded THRESHOLD


def get_embedding(image_bytes):
    if not image_bytes:
        return None
    
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    faces = face_app.get(img)
    if not faces:
        return None

    return faces[0].embedding

def find_match(embedding):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT cm.id, cm.name, cfe.embedding <=> %s::vector AS distance
            FROM crew_face_embeddings cfe
            JOIN crew_members cm ON cm.id = cfe.crew_member_id
            ORDER BY distance
            LIMIT 1;
        """, (embedding.tolist(),))

        row = cur.fetchone()
        if row:
            crew_member_id, name, distance = row
            return crew_member_id, name, distance

        return None, None, None
    except Exception as e:
        print(f"Error finding match: {e}")
        return None, None, None
    finally:
        cur.close()
        conn.close()

def register_user(name, embedding, aadhaar_number=None, contact_number=None, emergency_contact_number=None):
    """Register a new crew member with an initial face embedding."""
    crew_member_id = str(uuid.uuid4())
    emb_id = str(uuid.uuid4())

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO crew_members (id, name, aadhaar_number, phone, emergency_contact_number) VALUES (%s, %s, %s, %s, %s)",
            (crew_member_id, name, aadhaar_number, contact_number, emergency_contact_number)
        )
        cur.execute(
            "INSERT INTO crew_face_embeddings (id, crew_member_id, embedding) VALUES (%s, %s, %s)",
            (emb_id, crew_member_id, embedding.tolist())
        )
        conn.commit()
        return crew_member_id
    except Exception as e:
        conn.rollback()
        print(f"Error registering user: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def add_face_embedding(crew_member_id, embedding):
    """Add an additional face embedding for an existing crew member."""
    emb_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO crew_face_embeddings (id, crew_member_id, embedding) VALUES (%s, %s, %s)",
            (emb_id, crew_member_id, embedding.tolist())
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error adding face embedding: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_user_id_by_name(name):
    """Get crew_member_id by crew member name"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM crew_members WHERE name = %s LIMIT 1", (name,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting user by name: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_all_crew_members(skip=0, limit=100):
    """List all crew members."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, name, aadhaar_number, phone, emergency_contact_number 
            FROM crew_members 
            ORDER BY created_at DESC 
            OFFSET %s LIMIT %s
        """, (skip, limit))
        rows = cur.fetchall()
        
        crew_members = []
        for row in rows:
            crew_members.append({
                "id": str(row[0]),
                "name": row[1],
                "aadhaar_number": row[2],
                "contact_number": row[3],
                "emergency_contact_number": row[4]
            })
        return crew_members
    except Exception as e:
        print(f"Error listing crew members: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_crew_member_by_id(crew_member_id):
    """Get details of a specific crew member."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, name, aadhaar_number, phone, emergency_contact_number 
            FROM crew_members 
            WHERE id = %s
        """, (crew_member_id,))
        row = cur.fetchone()
        
        if row:
            return {
                "id": str(row[0]),
                "name": row[1],
                "aadhaar_number": row[2],
                "contact_number": row[3],
                "emergency_contact_number": row[4]
            }
        return None
    except Exception as e:
        print(f"Error getting crew member: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_crew_member(crew_member_id, name=None, aadhaar_number=None, contact_number=None, emergency_contact_number=None):
    """Update a crew member's details."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Build query dynamically based on provided fields
        fields = []
        values = []
        
        if name is not None:
            fields.append("name = %s")
            values.append(name)
        
        if aadhaar_number is not None:
            fields.append("aadhaar_number = %s")
            values.append(aadhaar_number)

        if contact_number is not None:
            fields.append("phone = %s")
            values.append(contact_number)

        if emergency_contact_number is not None:
            fields.append("emergency_contact_number = %s")
            values.append(emergency_contact_number)
            
        if not fields:
            return True # Nothing to update
            
        values.append(crew_member_id)
        
        query = f"UPDATE crew_members SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s"
        
        cur.execute(query, tuple(values))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error updating crew member: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def delete_crew_member(crew_member_id):
    """Delete a crew member."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM crew_members WHERE id = %s", (crew_member_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error deleting crew member: {e}")
        return False
    finally:
        cur.close()
        conn.close()
