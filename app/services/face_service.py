import io
import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw
from ultralytics import YOLO

from app.core.config import settings
from app.db.session import get_db_connection


@lru_cache
def _get_face_app() -> FaceAnalysis:
    """
    Initialize and cache InsightFace FaceAnalysis.

    Model name and device are configurable via settings so we can easily
    switch to different InsightFace/YOLO-based pipelines as per
    FACE_RECOGNITION_SYSTEM_UPGRADE_2026.md without changing call sites.
    """
    app = FaceAnalysis(name=settings.FACE_MODEL_NAME)
    # det_size left default so it can auto-select based on model;
    # ctx_id controls GPU / CPU usage.
    app.prepare(ctx_id=settings.FACE_CTX_ID)
    return app


@lru_cache
def _get_yolo_model() -> Optional[YOLO]:
    """
    Initialize and cache YOLO model for human detection.

    If YOLO is disabled via settings, returns None so callers can fall back
    to pure face detection.
    """
    if not settings.YOLO_ENABLED:
        return None
    model = YOLO(settings.YOLO_MODEL_NAME)
    return model


def _decode_image(image_bytes: bytes) -> Optional[np.ndarray]:
    if not image_bytes:
        return None

    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return img


def draw_face_boxes_on_image(
    image_bytes: bytes,
    faces: List[Dict[str, Any]],
    box_width: int = 4,
) -> Optional[bytes]:
    """
    Draw bounding boxes on the image using PIL. Green = match, red = no match.
    Each face dict must have 'bbox' ([x1, y1, x2, y2]) and 'is_match' (bool).
    Returns PNG image bytes, or None if the image cannot be opened.
    """
    if not image_bytes or not faces:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    draw = ImageDraw.Draw(img)
    for f in faces:
        bbox = f.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = [int(round(x)) for x in bbox]
        is_match = bool(f.get("is_match"))
        color = (0, 255, 0) if is_match else (255, 0, 0)  # green / red
        draw.rectangle(
            [x1, y1, x2, y2],
            outline=color,
            width=box_width,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_embedding(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Backwards‑compatible helper for single‑face flows (registration).
    Uses the first detected face embedding.
    """
    img = _decode_image(image_bytes)
    if img is None:
        return None

    face_app = _get_face_app()

    faces = face_app.get(img)
    if not faces:
        return None

    return faces[0].embedding


def identify_faces_in_image(
    image_bytes: bytes,
) -> Optional[Dict[str, Any]]:
    """
    Detect and identify multiple faces in a group photo.

    Returns a dict with a `faces` list. Each face entry contains:
      - bbox: [x1, y1, x2, y2]
      - det_score: detector confidence
      - distance: pgvector distance to closest stored embedding (or None)
      - is_match: bool using settings.FACE_MATCH_THRESHOLD
      - crew_member: dict with crew details if matched, else None
    """
    img = _decode_image(image_bytes)
    if img is None:
        return None

    face_app = _get_face_app()
    yolo_model = _get_yolo_model()

    results: List[Dict[str, Any]] = []

    if yolo_model is not None:
        # ---- Stage 1: YOLO human detection ----
        yolo_results = yolo_model(img)
        if not yolo_results:
            return {"faces": []}

        person_boxes: List[Tuple[int, int, int, int]] = []
        for r in yolo_results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls = int(box.cls[0].item()) if hasattr(box, "cls") else -1
                conf = float(box.conf[0].item()) if hasattr(box, "conf") else 0.0
                # COCO class 0 = person
                if cls == 0 and conf >= settings.YOLO_CONF_THRESHOLD:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    person_boxes.append(
                        (int(x1), int(y1), int(x2), int(y2))
                    )

        if not person_boxes:
            return {"faces": []}

        # ---- Stage 2: Face detection inside each person box ----
        for (px1, py1, px2, py2) in person_boxes:
            # Clamp to image bounds
            h, w = img.shape[:2]
            px1c = max(0, min(px1, w - 1))
            py1c = max(0, min(py1, h - 1))
            px2c = max(px1c + 1, min(px2, w))
            py2c = max(py1c + 1, min(py2, h))

            person_crop = img[py1c:py2c, px1c:px2c]
            if person_crop.size == 0:
                continue

            faces = face_app.get(person_crop)
            for face in faces:
                embedding = face.embedding
                crew_id, _, distance = find_match(embedding)

                is_match = False
                crew_member: Optional[Dict[str, Any]] = None
                if distance is not None and distance <= settings.FACE_MATCH_THRESHOLD and crew_id:
                    crew_member = get_crew_member_by_id(str(crew_id))
                    is_match = crew_member is not None

                # Face bbox is relative to the crop; convert to full-image coords
                local_bbox = getattr(face, "bbox", None)
                if local_bbox is not None:
                    fx1, fy1, fx2, fy2 = local_bbox
                    bbox = [
                        float(px1c + fx1),
                        float(py1c + fy1),
                        float(px1c + fx2),
                        float(py1c + fy2),
                    ]
                else:
                    bbox = [float(px1c), float(py1c), float(px2c), float(py2c)]

                det_score = float(getattr(face, "det_score", 0.0))

                results.append(
                    {
                        "bbox": bbox,
                        "det_score": det_score,
                        "distance": float(distance) if distance is not None else None,
                        "is_match": is_match,
                        "crew_member": crew_member,
                    }
                )
    else:
        # Fallback: direct face detection on the full frame (no YOLO)
        faces = face_app.get(img)
        if not faces:
            return {"faces": []}

        for face in faces:
            embedding = face.embedding
            crew_id, _, distance = find_match(embedding)

            is_match = False
            crew_member: Optional[Dict[str, Any]] = None
            if distance is not None and distance <= settings.FACE_MATCH_THRESHOLD and crew_id:
                crew_member = get_crew_member_by_id(str(crew_id))
                is_match = crew_member is not None

            bbox = [float(x) for x in getattr(face, "bbox", [])] if getattr(face, "bbox", None) is not None else None
            det_score = float(getattr(face, "det_score", 0.0))

            results.append(
                {
                    "bbox": bbox,
                    "det_score": det_score,
                    "distance": float(distance) if distance is not None else None,
                    "is_match": is_match,
                    "crew_member": crew_member,
                }
            )

    matched_count = sum(1 for r in results if r["is_match"])
    unmatched_count = len(results) - matched_count

    return {
        "faces": results,
        "summary": {
            "total_faces": len(results),
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
        },
    }

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

def register_user_minimal(
    name: str,
    aadhaar_number: str,
    contact_number: Optional[str] = None,
    emergency_contact_number: Optional[str] = None,
    is_pilot: bool = False,
) -> Optional[str]:
    """
    Register a crew member with minimum info (officer flow, no face).
    is_register is always set to False. Returns crew_member_id or None.
    """
    aadhaar = (aadhaar_number or "").strip()
    if not aadhaar:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM crew_members WHERE aadhaar_number = %s AND deleted_at IS NULL LIMIT 1", (aadhaar,))
        if cur.fetchone():
            return None  # Duplicate aadhaar; caller may treat as conflict
        crew_member_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO crew_members (id, name, aadhaar_number, phone, emergency_contact_number, is_pilot, is_register)
               VALUES (%s, %s, %s, %s, %s, %s, false)""",
            (
                crew_member_id,
                (name or "").strip(),
                aadhaar,
                (contact_number or "").strip() or None,
                (emergency_contact_number or "").strip() or None,
                is_pilot,
            ),
        )
        conn.commit()
        return crew_member_id
    except Exception as e:
        conn.rollback()
        print(f"Error in register_user_minimal: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def register_user(name, embedding, aadhaar_number=None, contact_number=None, emergency_contact_number=None, is_pilot=False):
    """Register a new crew member with an initial face embedding. Sets is_register=true (full registration)."""
    crew_member_id = str(uuid.uuid4())
    emb_id = str(uuid.uuid4())

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO crew_members (id, name, aadhaar_number, phone, emergency_contact_number, is_pilot, is_register)
               VALUES (%s, %s, %s, %s, %s, %s, true)""",
            (crew_member_id, name, aadhaar_number, contact_number, emergency_contact_number, is_pilot),
        )
        cur.execute(
            "INSERT INTO crew_face_embeddings (id, crew_member_id, embedding) VALUES (%s, %s, %s)",
            (emb_id, crew_member_id, embedding.tolist()),
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
            SELECT id, name, aadhaar_number, phone, emergency_contact_number, is_pilot, is_register
            FROM crew_members
            WHERE deleted_at IS NULL
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
                "emergency_contact_number": row[4],
                "is_pilot": row[5] if len(row) > 5 else False,
                "is_register": row[6] if len(row) > 6 else False,
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
            SELECT id, name, aadhaar_number, phone, emergency_contact_number, is_pilot, is_register
            FROM crew_members
            WHERE id = %s AND deleted_at IS NULL
        """, (crew_member_id,))
        row = cur.fetchone()

        if row:
            return {
                "id": str(row[0]),
                "name": row[1],
                "aadhaar_number": row[2],
                "contact_number": row[3],
                "emergency_contact_number": row[4],
                "is_pilot": row[5] if len(row) > 5 else False,
                "is_register": row[6] if len(row) > 6 else False,
            }
        return None
    except Exception as e:
        print(f"Error getting crew member: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_crew_member(crew_member_id, name=None, aadhaar_number=None, contact_number=None, emergency_contact_number=None, is_pilot=None):
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

        if is_pilot is not None:
            fields.append("is_pilot = %s")
            values.append(is_pilot)
            
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
