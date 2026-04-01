"""Save uploaded boat documents (PDF or image) to disk. Returns path to store in DB."""
import json
import os
import re
import uuid
from typing import List, Optional, Tuple

# Allowed MIME types for boat document
ALLOWED_BOAT_DOCUMENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
MAX_BOAT_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB


def _sanitize_filename(name: str) -> str:
    """Keep only safe chars; avoid path traversal."""
    base = os.path.basename(name) if "/" in name or "\\" in name else name
    safe = re.sub(r"[^\w.\-]", "_", base)
    return safe[:100] or "document"


def save_boat_document(
    boat_id: str,
    content: bytes,
    content_type: str,
    original_filename: str,
    upload_root: Optional[str] = None,
) -> Optional[Tuple[str, str, str]]:
    """
    Save boat document to uploads/boats/<boat_id>/<safe_filename>.
    Returns (relative_path, content_type, filename) or None on failure.
    """
    if content_type not in ALLOWED_BOAT_DOCUMENT_TYPES:
        return None
    if len(content) > MAX_BOAT_DOCUMENT_SIZE:
        return None
    root = upload_root or os.path.join(os.getcwd(), "uploads", "boats")
    dir_path = os.path.join(root, boat_id)
    os.makedirs(dir_path, exist_ok=True)
    ext = os.path.splitext(_sanitize_filename(original_filename))[1] or _ext_for_content_type(content_type)
    safe_name = _sanitize_filename(original_filename) or "document"
    if not safe_name.endswith(ext):
        safe_name = f"{safe_name}{ext}"
    # Avoid overwrite: add short unique suffix if needed
    file_path = os.path.join(dir_path, safe_name)
    if os.path.exists(file_path):
        stem, e = os.path.splitext(safe_name)
        safe_name = f"{stem}_{uuid.uuid4().hex[:8]}{e}"
        file_path = os.path.join(dir_path, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)
    # Store URL path (served by FastAPI StaticFiles): /uploads/boats/<boat_id>/<filename>
    url_path = f"/uploads/boats/{boat_id}/{os.path.basename(file_path)}"
    return (url_path, content_type, original_filename[:255])


def _ext_for_content_type(ct: str) -> str:
    if ct == "application/pdf":
        return ".pdf"
    if ct in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if ct == "image/png":
        return ".png"
    return ".bin"


def save_crew_crop(crop_id: str, content: bytes, upload_root: Optional[str] = None) -> bool:
    """
    Save crew face crop to uploads/crew-crops/<crop_id>.png.
    Persists crops so they survive server restarts (used for register with crop_image_url).
    """
    if not crop_id or not content:
        return False
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-crops")
    os.makedirs(root, exist_ok=True)
    file_path = os.path.join(root, f"{crop_id}.png")
    try:
        with open(file_path, "wb") as f:
            f.write(content)
        return True
    except OSError:
        return False


def load_crew_crop(crop_id: str, upload_root: Optional[str] = None) -> Optional[bytes]:
    """Load crew face crop from disk. Returns None if not found."""
    if not crop_id:
        return None
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-crops")
    file_path = os.path.join(root, f"{crop_id}.png")
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except OSError:
        return None


def get_crew_crop_static_path(crop_id: Optional[str], upload_root: Optional[str] = None) -> Optional[str]:
    """
    Return the static /uploads path for a crew crop only when the file exists.
    """
    if not crop_id:
        return None
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-crops")
    file_path = os.path.join(root, f"{crop_id}.png")
    if not os.path.exists(file_path):
        return None
    return f"/uploads/crew-crops/{crop_id}.png"


def save_crew_embedding(crop_id: str, embedding: List[float], upload_root: Optional[str] = None) -> bool:
    """Save face embedding for a crop. Used when registering from scan-group-photo."""
    if not crop_id or not embedding:
        return False
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-crops")
    os.makedirs(root, exist_ok=True)
    file_path = os.path.join(root, f"{crop_id}.embedding.json")
    try:
        with open(file_path, "w") as f:
            json.dump(embedding, f)
        return True
    except OSError:
        return False


def load_crew_embedding(crop_id: str, upload_root: Optional[str] = None) -> Optional[List[float]]:
    """Load face embedding for a crop. Returns None if not found."""
    if not crop_id:
        return None
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-crops")
    file_path = os.path.join(root, f"{crop_id}.embedding.json")
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_crew_scan_image(content: bytes, upload_root: Optional[str] = None) -> Optional[str]:
    """
    Save annotated crew scan image (PNG with face boxes) to uploads/crew-scan/<uuid>.png.
    Returns URL path for static serving, e.g. /uploads/crew-scan/<uuid>.png.
    """
    if not content:
        return None
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-scan")
    os.makedirs(root, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    file_path = os.path.join(root, name)
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except OSError:
        return None
    return f"/uploads/crew-scan/{name}"


def save_crew_scan_image_with_id(scan_id: str, content: bytes, upload_root: Optional[str] = None) -> Optional[str]:
    """
    Save annotated crew scan image to uploads/crew-scan/<scan_id>.png.
    Returns URL path for static serving, e.g. /uploads/crew-scan/<scan_id>.png.
    """
    if not scan_id or not content:
        return None
    root = upload_root or os.path.join(os.getcwd(), "uploads", "crew-scan")
    os.makedirs(root, exist_ok=True)
    file_path = os.path.join(root, f"{scan_id}.png")
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except OSError:
        return None
    return f"/uploads/crew-scan/{scan_id}.png"
