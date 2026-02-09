import cv2
import numpy as np
import uuid
from insightface.app import FaceAnalysis
from app.database import conn

app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0)

THRESHOLD = 0.6


def get_embedding(image_bytes):
    if not image_bytes:
        return None
    
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    faces = app.get(img)
    if not faces:
        return None

    return faces[0].embedding


def find_match(embedding):
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

        # 👇 ALWAYS return 3 values
        return None, None, None

    except Exception as e:
        conn.rollback()
        return None, None, None




def register_user(name, embedding):
    """Register a new crew member with an initial face embedding."""
    crew_member_id = str(uuid.uuid4())
    emb_id = str(uuid.uuid4())

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO crew_members (id, name) VALUES (%s, %s)",
        (crew_member_id, name)
    )
    cur.execute(
        "INSERT INTO crew_face_embeddings (id, crew_member_id, embedding) VALUES (%s, %s, %s)",
        (emb_id, crew_member_id, embedding.tolist())
    )

    conn.commit()
    return crew_member_id


def add_face_embedding(crew_member_id, embedding):
    """Add an additional face embedding for an existing crew member."""
    emb_id = str(uuid.uuid4())
    
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


def get_user_id_by_name(name):
    """Get crew_member_id by crew member name"""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM crew_members WHERE name = %s LIMIT 1", (name,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting user by name: {e}")
        return None
