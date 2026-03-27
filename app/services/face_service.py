import io
import logging
import uuid
from functools import lru_cache
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageOps

from app.core.config import settings
from app.db.session import get_db_connection

# Set to False after verifying mobile orientation/crop fixes.
FACE_DEBUG_LOGS = True
logger = logging.getLogger(__name__)


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
def _get_yolo_model() -> Optional[Any]:
    """
    Initialize and cache YOLO model for human detection.

    If YOLO is disabled via settings, returns None so callers can fall back
    to pure face detection.
    """
    if not settings.YOLO_ENABLED:
        return None

    # Lazy import so Ultralytics / PyTorch are only loaded when YOLO
    # is actually enabled and used (saves baseline RAM on small hosts).
    from ultralytics import YOLO

    model = YOLO(settings.YOLO_MODEL_NAME)
    return model


def _load_normalized_image(image_bytes: bytes) -> Optional[Tuple[Image.Image, int]]:
    """
    Load image with EXIF orientation applied. Returns (PIL Image in RGB, exif_orientation).
    This ensures all downstream ops use the same display-oriented pixel matrix.
    """
    if not image_bytes:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_orientation = 1
        try:
            exif = img.getexif() if hasattr(img, "getexif") else None
            exif_orientation = exif.get(274, 1) if exif else 1
        except Exception:
            pass
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        return img, exif_orientation
    except Exception:
        return None


def _pil_to_cv2_bgr(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL RGB to OpenCV BGR for InsightFace/YOLO."""
    arr = np.array(pil_img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _scale_bbox_to_original(
    bbox: List[float],
    det_w: int,
    det_h: int,
    orig_w: int,
    orig_h: int,
) -> List[float]:
    """Scale bbox from detection (possibly scaled) space to original normalized image space."""
    if det_w <= 0 or det_h <= 0:
        return bbox
    sx = orig_w / det_w
    sy = orig_h / det_h
    return [
        bbox[0] * sx,
        bbox[1] * sy,
        bbox[2] * sx,
        bbox[3] * sy,
    ]


def _decode_image(
    image_bytes: bytes,
) -> Optional[Tuple[np.ndarray, int, int, int, int]]:
    """
    Load image with EXIF normalization, convert to BGR for detection, optionally scale.
    Returns (scaled_numpy_bgr, det_w, det_h, orig_w, orig_h) for bbox coordinate mapping.
    """
    if not image_bytes:
        return None

    norm = _load_normalized_image(image_bytes)
    if norm is None:
        return None
    pil_img, exif_orientation = norm
    orig_w, orig_h = pil_img.size
    img = _pil_to_cv2_bgr(pil_img)
    h, w = img.shape[:2]

    if FACE_DEBUG_LOGS:
        logger.info(
            "[face] input image size=(%d,%d) mode=RGB exif_orientation=%s",
            orig_w,
            orig_h,
            exif_orientation,
        )

    target_max_side = max(256, int(settings.FACE_DETECT_MAX_SIDE or 512))
    max_side = max(h, w)
    if max_side > target_max_side:
        scale = float(target_max_side) / float(max_side)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        det_w, det_h = new_w, new_h
    else:
        det_w, det_h = w, h

    return img, det_w, det_h, orig_w, orig_h


def _iou_xyxy(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    """Compute IoU of two boxes in xyxy format [x1, y1, x2, y2]."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def _nms_boxes_xyxy(
    boxes: List[Tuple[int, int, int, int]],
    scores: List[float],
    iou_threshold: float = 0.5,
) -> List[int]:
    """
    Non-maximum suppression on xyxy boxes. YOLO26 is NMS-free and can return
    overlapping detections for the same person; this merges duplicates.
    Returns indices of boxes to keep (sorted by score descending).
    """
    if not boxes or not scores:
        return []
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    kept: List[int] = []
    for i in order:
        box_i = boxes[i]
        suppress = False
        for j in kept:
            if _iou_xyxy(
                (float(box_i[0]), float(box_i[1]), float(box_i[2]), float(box_i[3])),
                (float(boxes[j][0]), float(boxes[j][1]), float(boxes[j][2]), float(boxes[j][3])),
            ) > iou_threshold:
                suppress = True
                break
        if not suppress:
            kept.append(i)
    return kept


def _deduplicate_faces_by_iou(
    faces: List[Dict[str, Any]],
    iou_threshold: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Merge face entries that refer to the same face (high bbox overlap).
    Keeps the face with higher det_score when merging.
    """
    if len(faces) <= 1:
        return faces
    kept: List[Dict[str, Any]] = []
    for f in faces:
        bbox = f.get("bbox")
        if not bbox or len(bbox) != 4:
            kept.append(f)
            continue
        box = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        score = float(f.get("det_score") or 0.0)
        duplicate_of = None
        for i, k in enumerate(kept):
            kb = k.get("bbox")
            if not kb or len(kb) != 4:
                continue
            kbox = (float(kb[0]), float(kb[1]), float(kb[2]), float(kb[3]))
            if _iou_xyxy(box, kbox) >= iou_threshold:
                if score > float(k.get("det_score") or 0.0):
                    duplicate_of = i
                else:
                    duplicate_of = -1
                break
        if duplicate_of is None:
            kept.append(f)
        elif duplicate_of >= 0:
            kept[duplicate_of] = f
    return kept


def draw_face_boxes_on_image(
    image_bytes: bytes,
    faces: List[Dict[str, Any]],
    box_width: int = 4,
    normalized_image: Optional[Image.Image] = None,
) -> Optional[bytes]:
    """
    Draw bounding boxes on the image using PIL. Green = match, red = no match.
    Each face dict must have 'bbox' ([x1, y1, x2, y2]) in normalized image coords.
    Uses EXIF-normalized image so output displays correctly on mobile.
    Returns PNG image bytes (no EXIF, display orientation baked in).
    """
    if not image_bytes or not faces:
        return None
    if normalized_image is not None:
        img = normalized_image.copy()
    else:
        norm = _load_normalized_image(image_bytes)
        if norm is None:
            return None
        img, _ = norm
    w, h = img.size

    draw = ImageDraw.Draw(img)
    for f in faces:
        bbox = f.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = [int(round(x)) for x in bbox]
        # Clamp to image bounds
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))
        is_match = bool(f.get("is_match"))
        color = (0, 255, 0) if is_match else (255, 0, 0)  # green / red
        draw.rectangle(
            [x1, y1, x2, y2],
            outline=color,
            width=box_width,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out_bytes = buf.getvalue()
    if FACE_DEBUG_LOGS:
        logger.info("[face] draw_face_boxes output size=(%d,%d)", w, h)
    return out_bytes


def crop_face_from_image(
    image_bytes: bytes,
    bbox: List[float],
    normalized_image: Optional[Image.Image] = None,
) -> Optional[bytes]:
    """
    Crop the face/person region from the image using bbox [x1, y1, x2, y2].
    Bbox must be in normalized (EXIF-applied) image coordinates.
    Returns PNG image bytes (no EXIF) for correct mobile display.
    """
    if not image_bytes or not bbox or len(bbox) != 4:
        return None
    if normalized_image is not None:
        img = normalized_image
    else:
        norm = _load_normalized_image(image_bytes)
        if norm is None:
            return None
        img, _ = norm
    w, h = img.size
    x1, y1, x2, y2 = [int(round(x)) for x in bbox]
    # Clamp to image bounds: left>=0, top>=0, right<=width, bottom<=height
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = img.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    out_bytes = buf.getvalue()
    if FACE_DEBUG_LOGS:
        logger.info(
            "[face] crop_face final_rect=(%d,%d,%d,%d) img_size=(%d,%d) crop_size=(%d,%d)",
            x1,
            y1,
            x2,
            y2,
            w,
            h,
            x2 - x1,
            y2 - y1,
        )
    return out_bytes


def detect_face_and_crop(image_bytes: bytes) -> Tuple[bool, Optional[bytes]]:
    """
    Detect a single face in the image and return a cropped face image.

    Returns:
        (face_detected, crop_bytes): face_detected is True if a face was found,
        crop_bytes is PNG bytes of the cropped face (or None if no face).
    """
    decoded = _decode_image(image_bytes)
    if decoded is None:
        return False, None
    img, det_w, det_h, orig_w, orig_h = decoded

    face_app = _get_face_app()
    faces = face_app.get(img)
    if not faces:
        return False, None

    face = faces[0]
    bbox = getattr(face, "bbox", None)
    if bbox is None or len(bbox) != 4:
        return False, None

    bbox_orig = _scale_bbox_to_original(
        [float(x) for x in bbox], det_w, det_h, orig_w, orig_h
    )
    if FACE_DEBUG_LOGS:
        logger.info(
            "[face] detect_face_and_crop bbox_det=%s bbox_orig=%s",
            bbox,
            bbox_orig,
        )
    crop_bytes = crop_face_from_image(image_bytes, bbox_orig)
    if not crop_bytes:
        return False, None

    return True, crop_bytes


def get_embedding(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Backwards‑compatible helper for single‑face flows (registration).
    Uses the first detected face embedding.
    """
    decoded = _decode_image(image_bytes)
    if decoded is None:
        return None
    img, _, _, _, _ = decoded

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
      - bbox: [x1, y1, x2, y2] in normalized (original) image coordinates
      - det_score: detector confidence
      - distance: pgvector distance to closest stored embedding (or None)
      - is_match: bool using settings.FACE_MATCH_THRESHOLD
      - crew_member: dict with crew details if matched, else None
    """
    decoded = _decode_image(image_bytes)
    if decoded is None:
        return None
    img, det_w, det_h, orig_w, orig_h = decoded

    face_app = _get_face_app()
    yolo_model = _get_yolo_model()

    results: List[Dict[str, Any]] = []
    match_total_ms = 0.0
    crew_fetch_total_ms = 0.0

    def _scale_and_append(bbox_det: List[float], **kwargs: Any) -> None:
        bbox_orig = _scale_bbox_to_original(
            bbox_det, det_w, det_h, orig_w, orig_h
        )
        if FACE_DEBUG_LOGS and results:
            pass  # Log once per batch below
        results.append({"bbox": bbox_orig, **kwargs})

    if yolo_model is not None:
        # ---- Stage 1: YOLO human detection ----
        yolo_results = yolo_model(img)
        if not yolo_results:
            return {"faces": []}

        person_boxes: List[Tuple[int, int, int, int]] = []
        person_scores: List[float] = []
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
                    person_scores.append(conf)

        if not person_boxes:
            return {"faces": []}

        nms_keep = _nms_boxes_xyxy(person_boxes, person_scores, iou_threshold=0.5)
        person_boxes = [person_boxes[i] for i in nms_keep]

        if FACE_DEBUG_LOGS:
            logger.info(
                "[face] identify_faces det_size=(%d,%d) orig_size=(%d,%d) person_boxes=%d",
                det_w,
                det_h,
                orig_w,
                orig_h,
                len(person_boxes),
            )

        # ---- Stage 2: Face detection inside each person box ----
        for (px1, py1, px2, py2) in person_boxes:
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
                match_start = perf_counter()
                crew_member, distance = find_match(embedding)
                match_total_ms += (perf_counter() - match_start) * 1000.0

                is_match = False
                if distance is not None and distance <= settings.FACE_MATCH_THRESHOLD and crew_member:
                    is_match = True
                else:
                    crew_member = None

                local_bbox = getattr(face, "bbox", None)
                if local_bbox is not None:
                    fx1, fy1, fx2, fy2 = local_bbox
                    bbox_det = [
                        float(px1c + fx1),
                        float(py1c + fy1),
                        float(px1c + fx2),
                        float(py1c + fy2),
                    ]
                else:
                    bbox_det = [float(px1c), float(py1c), float(px2c), float(py2c)]

                det_score = float(getattr(face, "det_score", 0.0))
                _scale_and_append(
                    bbox_det,
                    det_score=det_score,
                    distance=float(distance) if distance is not None else None,
                    is_match=is_match,
                    crew_member=crew_member,
                    embedding=embedding.tolist(),
                )
        results = _deduplicate_faces_by_iou(results, iou_threshold=0.4)
    else:
        # Fallback: direct face detection on the full frame (no YOLO)
        faces = face_app.get(img)
        if not faces:
            return {"faces": []}

        if FACE_DEBUG_LOGS:
            logger.info(
                "[face] identify_faces (no YOLO) det_size=(%d,%d) orig_size=(%d,%d)",
                det_w,
                det_h,
                orig_w,
                orig_h,
            )

        for face in faces:
            embedding = face.embedding
            match_start = perf_counter()
            crew_member, distance = find_match(embedding)
            match_total_ms += (perf_counter() - match_start) * 1000.0

            is_match = False
            if distance is not None and distance <= settings.FACE_MATCH_THRESHOLD and crew_member:
                is_match = True
            else:
                crew_member = None

            bbox_det = (
                [float(x) for x in getattr(face, "bbox", [])]
                if getattr(face, "bbox", None) is not None
                else None
            )
            det_score = float(getattr(face, "det_score", 0.0))
            if bbox_det and len(bbox_det) == 4:
                _scale_and_append(
                    bbox_det,
                    det_score=det_score,
                    distance=float(distance) if distance is not None else None,
                    is_match=is_match,
                    crew_member=crew_member,
                    embedding=embedding.tolist(),
                )
            else:
                results.append(
                    {
                        "bbox": None,
                        "det_score": det_score,
                        "distance": float(distance) if distance is not None else None,
                        "is_match": is_match,
                        "crew_member": crew_member,
                        "embedding": embedding.tolist(),
                    }
                )
        results = _deduplicate_faces_by_iou(results, iou_threshold=0.4)

    matched_count = sum(1 for r in results if r["is_match"])
    unmatched_count = len(results) - matched_count

    return {
        "faces": results,
        "summary": {
            "total_faces": len(results),
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "find_match_total_ms": match_total_ms,
            # Crew data now comes from find_match join, so this remains 0 by design.
            "crew_fetch_total_ms": crew_fetch_total_ms,
        },
    }

def find_match(embedding: np.ndarray) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                cm.id,
                cm.name,
                cm.aadhaar_number,
                cm.email,
                cm.phone,
                cm.emergency_contact_number,
                cm.is_pilot,
                cm.is_register,
                cfe.embedding <=> %s::vector AS distance
            FROM crew_face_embeddings cfe
            JOIN crew_members cm ON cm.id = cfe.crew_member_id
            WHERE cm.deleted_at IS NULL
            ORDER BY distance
            LIMIT 1;
        """, (embedding.tolist(),))

        row = cur.fetchone()
        if row:
            return {
                "id": str(row[0]),
                "name": row[1],
                "aadhaar_number": row[2],
                "email": row[3],
                "contact_number": row[4],
                "emergency_contact_number": row[5],
                "is_pilot": row[6] if row[6] is not None else False,
                "is_register": row[7] if row[7] is not None else False,
            }, float(row[8]) if row[8] is not None else None

        return None, None
    except Exception as e:
        print(f"Error finding match: {e}")
        return None, None
    finally:
        cur.close()
        conn.close()


def get_normalized_pil_image(image_bytes: bytes) -> Optional[Image.Image]:
    """Return EXIF-normalized RGB PIL image for reusing draw/crop in one request."""
    norm = _load_normalized_image(image_bytes)
    if norm is None:
        return None
    img, _ = norm
    return img

def register_user_minimal(
    name: str,
    aadhaar_number: str,
    contact_number: Optional[str] = None,
    emergency_contact_number: Optional[str] = None,
    is_pilot: bool = False,
    registered_by_user_id: Optional[str] = None,
    profile_crop_id: Optional[str] = None,
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
            """INSERT INTO crew_members (id, name, aadhaar_number, phone, emergency_contact_number, is_pilot, is_register, registered_by_user_id, profile_crop_id)
               VALUES (%s, %s, %s, %s, %s, %s, false, %s, %s)""",
            (
                crew_member_id,
                (name or "").strip(),
                aadhaar,
                (contact_number or "").strip() or None,
                (emergency_contact_number or "").strip() or None,
                is_pilot,
                registered_by_user_id,
                profile_crop_id,
            ),
        )
        if registered_by_user_id:
            cur.execute(
                """
                UPDATE users
                SET unregistered_crew_count = COALESCE(unregistered_crew_count, 0) + 1
                WHERE id = %s
                """,
                (registered_by_user_id,),
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


def register_user(
    name,
    embedding,
    aadhaar_number=None,
    contact_number=None,
    emergency_contact_number=None,
    is_pilot=False,
    registered_by_user_id: Optional[str] = None,
    profile_crop_id: Optional[str] = None,
):
    """Register a new crew member with an initial face embedding. Sets is_register=true (full registration)."""
    crew_member_id = str(uuid.uuid4())
    emb_id = str(uuid.uuid4())

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO crew_members (id, name, aadhaar_number, phone, emergency_contact_number, is_pilot, is_register, registered_by_user_id, profile_crop_id)
               VALUES (%s, %s, %s, %s, %s, %s, true, %s, %s)""",
            (
                crew_member_id,
                name,
                aadhaar_number,
                contact_number,
                emergency_contact_number,
                is_pilot,
                registered_by_user_id,
                profile_crop_id,
            ),
        )
        cur.execute(
            "INSERT INTO crew_face_embeddings (id, crew_member_id, embedding) VALUES (%s, %s, %s)",
            (emb_id, crew_member_id, embedding.tolist()),
        )
        if registered_by_user_id:
            cur.execute(
                """
                UPDATE users
                SET registered_crew_count = COALESCE(registered_crew_count, 0) + 1
                WHERE id = %s
                """,
                (registered_by_user_id,),
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

def get_all_crew_members(skip: int = 0, limit: int = 10, is_register: Optional[bool] = None):
    """List crew members with optional is_register filter and pagination."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT id, name, aadhaar_number, email, phone, emergency_contact_number, is_pilot, is_register
            FROM crew_members
            WHERE deleted_at IS NULL
        """
        params = []
        if is_register is not None:
            query += " AND is_register = %s"
            params.append(is_register)

        query += """
            ORDER BY created_at DESC
            OFFSET %s LIMIT %s
        """
        params.extend([skip, limit])

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        crew_members = []
        for row in rows:
            crew_members.append({
                "id": str(row[0]),
                "name": row[1],
                "aadhaar_number": row[2],
                "email": row[3],
                "contact_number": row[4],
                "emergency_contact_number": row[5],
                "is_pilot": row[6] if len(row) > 6 else False,
                "is_register": row[7] if len(row) > 7 else False,
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
            SELECT id, name, aadhaar_number, email, phone, emergency_contact_number, is_pilot, is_register
            FROM crew_members
            WHERE id = %s AND deleted_at IS NULL
        """, (crew_member_id,))
        row = cur.fetchone()

        if row:
            return {
                "id": str(row[0]),
                "name": row[1],
                "aadhaar_number": row[2],
                "email": row[3],
                "contact_number": row[4],
                "emergency_contact_number": row[5],
                "is_pilot": row[6] if len(row) > 6 else False,
                "is_register": row[7] if len(row) > 7 else False,
            }
        return None
    except Exception as e:
        print(f"Error getting crew member: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def get_unregistered_crew_member_for_phone(phone: str) -> Optional[Dict[str, Any]]:
    """
    Latest crew_members row for this phone with is_register=false (e.g. officer
    minimal register flow) — no row in pending_crew_registrations.
    """
    p = (phone or "").strip()
    if not p:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name, aadhaar_number, email, phone, emergency_contact_number, is_pilot, is_register
            FROM crew_members
            WHERE phone = %s AND is_register = false AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (p,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "name": row[1],
            "aadhaar_number": row[2],
            "email": row[3],
            "contact_number": row[4],
            "emergency_contact_number": row[5],
            "is_pilot": row[6] if len(row) > 6 else False,
            "is_register": row[7] if len(row) > 7 else False,
        }
    except Exception as e:
        logger.exception("get_unregistered_crew_member_for_phone: %s", e)
        return None
    finally:
        cur.close()
        conn.close()


def promote_crew_member_to_registered(crew_member_id: str) -> bool:
    """Set is_register=true and adjust officer registered/unregistered counts."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT registered_by_user_id, is_register
            FROM crew_members
            WHERE id = %s AND deleted_at IS NULL
            """,
            (crew_member_id,),
        )
        row = cur.fetchone()
        if not row:
            return False
        registered_by_user_id, is_reg = row[0], row[1]
        if is_reg is True:
            return True
        cur.execute(
            """
            UPDATE crew_members
            SET is_register = true, updated_at = NOW()
            WHERE id = %s AND is_register = false AND deleted_at IS NULL
            """,
            (crew_member_id,),
        )
        if cur.rowcount == 0:
            return False
        if registered_by_user_id:
            cur.execute(
                """
                UPDATE users
                SET unregistered_crew_count = GREATEST(COALESCE(unregistered_crew_count, 0) - 1, 0),
                    registered_crew_count = COALESCE(registered_crew_count, 0) + 1
                WHERE id = %s
                """,
                (registered_by_user_id,),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.exception("promote_crew_member_to_registered: %s", e)
        return False
    finally:
        cur.close()
        conn.close()


def update_crew_member(crew_member_id, name=None, aadhaar_number=None, contact_number=None, emergency_contact_number=None, is_pilot=None):
    """Update a crew member's details."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Optionally detect is_register promotion when needed in future:
        # current flow does not toggle is_register here, so counters do not change.
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
    """Delete a crew member and adjust officer counters."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch attributes needed for counter adjustment
        cur.execute(
            """
            SELECT registered_by_user_id, is_register
            FROM crew_members
            WHERE id = %s
            """,
            (crew_member_id,),
        )
        row = cur.fetchone()
        registered_by_user_id = row[0] if row else None
        is_register = row[1] if row and len(row) > 1 else None

        cur.execute("DELETE FROM crew_members WHERE id = %s", (crew_member_id,))

        if cur.rowcount > 0 and registered_by_user_id:
            if is_register is True:
                cur.execute(
                    """
                    UPDATE users
                    SET registered_crew_count = GREATEST(COALESCE(registered_crew_count, 0) - 1, 0)
                    WHERE id = %s
                    """,
                    (registered_by_user_id,),
                )
            elif is_register is False:
                cur.execute(
                    """
                    UPDATE users
                    SET unregistered_crew_count = GREATEST(COALESCE(unregistered_crew_count, 0) - 1, 0)
                    WHERE id = %s
                    """,
                    (registered_by_user_id,),
                )

        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error deleting crew member: {e}")
        return False
    finally:
        cur.close()
        conn.close()
