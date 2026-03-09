"""Boat number extraction from images using EasyOCR."""

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Indian fishing boat registration patterns:
#   IND-TN-12-MM-1234, TN-12-MM-1234, IND-KA-05-A-0032, etc.
#   Delimiters can be hyphen, space, or absent.
_BOAT_NUMBER_PATTERN = re.compile(
    r"""
    (?:IND[-\s]?)?          # optional country prefix
    [A-Z]{2}               # state code (TN, KA, KL, MH, GJ, AP …)
    [-\s]?
    \d{1,2}                # district code
    [-\s]?
    [A-Z]{1,3}             # category letters (MM, A, TT …)
    [-\s]?
    \d{1,5}                # serial number
    """,
    re.VERBOSE,
)


@lru_cache(maxsize=1)
def _get_ocr_reader() -> Any:
    """Lazy-init and cache the EasyOCR reader (heavy model load on first call)."""
    import easyocr
    reader = easyocr.Reader(["en"], gpu=False)
    return reader


def _preprocess_image(image_bytes: bytes) -> Optional[np.ndarray]:
    """Decode and enhance the image for better OCR accuracy."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced


def _normalize_boat_number(text: str) -> str:
    """Normalise OCR output to a clean boat number (uppercase, hyphen-separated)."""
    cleaned = text.upper().strip()
    cleaned = re.sub(r"[^A-Z0-9]", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = cleaned.strip("-")
    return cleaned


def scan_boat_number(image_bytes: bytes) -> Dict:
    """
    Run OCR on a boat image and extract the registration number.

    Returns dict with:
      - boat_number: best matched registration number (or None)
      - confidence: OCR confidence for that match
      - all_detected_text: every text string found in the image
    """
    processed = _preprocess_image(image_bytes)
    if processed is None:
        return {
            "boat_number": None,
            "confidence": None,
            "all_detected_text": [],
        }

    reader = _get_ocr_reader()
    results = reader.readtext(processed)

    all_texts: List[str] = []
    candidates: List[Dict] = []

    for bbox, text, confidence in results:
        all_texts.append(text)
        normalized = _normalize_boat_number(text)
        match = _BOAT_NUMBER_PATTERN.search(normalized)
        if match:
            candidates.append({
                "raw_text": text,
                "normalized": match.group(0),
                "confidence": float(confidence),
            })

    if not candidates:
        combined = " ".join(all_texts)
        combined_norm = _normalize_boat_number(combined)
        match = _BOAT_NUMBER_PATTERN.search(combined_norm)
        if match:
            candidates.append({
                "raw_text": combined,
                "normalized": match.group(0),
                "confidence": 0.0,
            })

    best = max(candidates, key=lambda c: c["confidence"]) if candidates else None

    if best:
        return {
            "boat_number": best["normalized"],
            "confidence": best["confidence"],
            "all_detected_text": all_texts,
        }

    # No pattern match -- fall back to the highest-confidence detected text
    if results:
        best_raw = max(results, key=lambda r: r[2])
        return {
            "boat_number": _normalize_boat_number(best_raw[1]),
            "confidence": float(best_raw[2]),
            "all_detected_text": all_texts,
        }

    return {
        "boat_number": None,
        "confidence": None,
        "all_detected_text": all_texts,
    }
