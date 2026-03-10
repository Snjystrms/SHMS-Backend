"""Helpers for building absolute image URLs."""
from typing import Optional

from app.core.config import settings


def get_base_url(request_base_url: Optional[str] = None) -> str:
    """
    Return the base URL for building absolute image URLs.
    Prefer PUBLIC_URL when set (production behind proxy); otherwise use request.base_url.
    """
    if settings.PUBLIC_URL:
        base = str(settings.PUBLIC_URL).rstrip("/")
        return base
    if request_base_url:
        return str(request_base_url).rstrip("/")
    return ""


def resolve_image_url(path: str, request_base_url: Optional[str] = None) -> Optional[str]:
    """
    Convert a path to an absolute URL.

    - path: e.g. /uploads/crew-scan/xxx.png or /api/v1/crew-members/scan-result/{id}/crop
    - request_base_url: str(request.base_url) from the request
    - Returns: absolute URL if path is valid; None if path is empty
    """
    if not path or not path.strip():
        return None
    path = path.strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = get_base_url(request_base_url)
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}" if base else path
"""Helpers for building absolute image URLs."""
from typing import Optional

from app.core.config import settings


def get_base_url(request_base_url: Optional[str] = None) -> str:
    """
    Return the base URL for building absolute image URLs.
    Prefer PUBLIC_URL when set (production behind proxy); otherwise use request.base_url.
    """
    if settings.PUBLIC_URL:
        base = str(settings.PUBLIC_URL).rstrip("/")
        return base
    if request_base_url:
        return str(request_base_url).rstrip("/")
    return ""


def resolve_image_url(path: str, request_base_url: Optional[str] = None) -> Optional[str]:
    """
    Convert a path to an absolute URL.

    - path: e.g. /uploads/crew-scan/xxx.png or /api/v1/crew-members/scan-result/{id}/crop
    - request_base_url: str(request.base_url) from the request
    - Returns: absolute URL if path is valid; None if path is empty
    """
    if not path or not path.strip():
        return None
    path = path.strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = get_base_url(request_base_url)
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}" if base else path