"""Save uploaded boat documents (PDF or image) to disk. Returns path to store in DB."""
import os
import re
import uuid
from typing import Tuple, Optional

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
