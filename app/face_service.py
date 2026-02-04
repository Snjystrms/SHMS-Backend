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
            SELECT u.id, u.name, fe.embedding <=> %s::vector AS distance
            FROM face_embeddings fe
            JOIN users u ON u.id = fe.user_id
            ORDER BY distance
            LIMIT 1;
        """, (embedding.tolist(),))

        row = cur.fetchone()

        if row:
            user_id, username, distance = row
            return user_id, username, distance

        # 👇 ALWAYS return 3 values
        return None, None, None

    except Exception as e:
        conn.rollback()
        return None, None, None




def register_user(name, embedding):
    user_id = str(uuid.uuid4())
    emb_id = str(uuid.uuid4())

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (id, name) VALUES (%s, %s)",
        (user_id, name)
    )
    cur.execute(
        "INSERT INTO face_embeddings (id, user_id, embedding) VALUES (%s, %s, %s)",
        (emb_id, user_id, embedding.tolist())
    )

    conn.commit()
    return user_id
