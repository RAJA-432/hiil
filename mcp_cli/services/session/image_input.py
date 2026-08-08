from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_cli.services.logging import get_logger

if TYPE_CHECKING:
    from mcp_cli.services.notification_bus import NotificationBus

logger = get_logger("chat")


class ImageInputHandler:
    async def augment_text(
        self,
        text: str,
        images: list[str] | None,
        can_process_images: Any,
        bus: NotificationBus | None,
    ) -> tuple[str, list[str] | None]:
        """OCR fallback for non-vision models. Returns (text, images to send)."""
        if not images:
            return text, images
        if await can_process_images():
            return text, images
        from mcp_cli.services.ocr import extract_text_from_data_url, is_available
        if is_available():
            ocr_texts = []
            for img_url in images:
                ocr_text = extract_text_from_data_url(img_url)
                if ocr_text:
                    ocr_texts.append(ocr_text)
            if ocr_texts:
                ocr_context = "\n\n[OCR text extracted from image(s)]:\n" + "\n---\n".join(ocr_texts)
                text = text + ocr_context
                if bus:
                    await bus.push_log("info", f"OCR extracted text from {len(ocr_texts)} image(s)")
            elif bus:
                await bus.push_log("warn", "OCR available but no text could be extracted from image(s)")
        else:
            if bus:
                await bus.push_log("warn", "OCR libraries not installed (pip install Pillow pytesseract). Cannot process images with this model.")
                await bus.push_log("drop", "Images ignored: model has no vision and OCR is unavailable.")
        return text, None

    def build_user_message(self, text: str, images: list[str] | None) -> tuple[Any, str]:
        """Build the user message content for text and/or image data-URLs."""
        if images:
            content: list[dict] = [{"type": "text", "text": text}]
            for img_url in images:
                content.append({"type": "image_url", "image_url": {"url": img_url}})
            return content, text
        return text, text
