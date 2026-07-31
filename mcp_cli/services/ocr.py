"""OCR service for extracting text from images.
Falls back gracefully when pytesseract/PIL are not installed.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("mcp_cli.services.ocr")

_HAS_PIL = False
_HAS_TESSERACT = False

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    Image = None  # type: ignore

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
    try:
        image_bytes = base64.b64decode(b64_data)
        return extract_text_from_image(image_bytes, language)
    except Exception as exc:
        logger.warning("Failed to decode data URL for OCR: %s", exc)
        return ""
