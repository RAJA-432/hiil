"""OCR service for extracting text from images.
Falls back gracefully when pytesseract/PIL are not installed.
"""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger("mcp_cli.services.ocr")

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000

_HAS_PIL = False
_HAS_TESSERACT = False

Image: Any = None
try:
    from PIL import Image as _Image
    Image = _Image
    _HAS_PIL = True
except ImportError:
    pass

try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    pytesseract = None


def is_available() -> bool:
    return _HAS_PIL and _HAS_TESSERACT


def extract_text_from_image(image_data: bytes, language: str = "eng") -> str:
    if not _HAS_PIL:
        logger.warning("PIL/Pillow not installed, OCR unavailable")
        return ""
    if not _HAS_TESSERACT:
        logger.warning("pytesseract not installed, OCR unavailable")
        return ""

    try:
        img = Image.open(io.BytesIO(image_data))
        if img.width * img.height > MAX_IMAGE_PIXELS:
            logger.warning("image too large for OCR: %dx%d pixels", img.width, img.height)
            return ""
        text = pytesseract.image_to_string(img, lang=language)
        return text.strip()
    except Exception as exc:
        logger.warning("OCR extraction failed: %s", exc)
        return ""


def extract_text_from_data_url(data_url: str, language: str = "eng") -> str:
    import base64
    if "," not in data_url:
        return ""
    header, b64_data = data_url.split(",", 1)
    if not header.lower().startswith("data:image/"):
        return ""
    try:
        image_bytes = base64.b64decode(b64_data)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            logger.warning("data URL image exceeds %d bytes, skipping OCR", MAX_IMAGE_BYTES)
            return ""
        return extract_text_from_image(image_bytes, language)
    except Exception as exc:
        logger.warning("Failed to decode data URL for OCR: %s", exc)
        return ""
