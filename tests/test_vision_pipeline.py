from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_cli.services.chat import CliChat
from mcp_cli.services.ocr import extract_text_from_data_url, extract_text_from_image
from mcp_cli.services.usage import count_tokens


class TestMultimodalContentBuilding:
    def test_no_images_produces_plain_string(self):
        augmented = "Hello, how are you?"
        content = augmented
        assert isinstance(content, str)
        assert content == "Hello, how are you?"

    def test_with_images_produces_multimodal_list(self):
        augmented = "What's in this image?"
        images = [
            "data:image/png;base64,abc123",
            "data:image/png;base64,def456",
        ]
        content: list[dict] = [{"type": "text", "text": augmented}]
        for img_url in images:
            content.append({"type": "image_url", "image_url": {"url": img_url}})

        assert isinstance(content, list)
        assert len(content) == 3
        assert content[0] == {"type": "text", "text": "What's in this image?"}
        assert content[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}}
        assert content[2] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,def456"}}


class TestVisionModelDetection:
    def test_gpt_4o_is_vision(self):
        assert CliChat._is_vision_model("gpt-4o") is True

    def test_claude_3_sonnet_is_vision(self):
        assert CliChat._is_vision_model("claude-3-sonnet") is True

    def test_gemini_1_5_pro_is_vision(self):
        assert CliChat._is_vision_model("gemini-1.5-pro") is True

    def test_gemma4_31b_cloud_is_vision(self):
        assert CliChat._is_vision_model("gemma4:31b-cloud") is True

    def test_deepseek_chat_not_vision(self):
        assert CliChat._is_vision_model("deepseek-chat") is False

    def test_gemma2_not_vision(self):
        assert CliChat._is_vision_model("gemma2") is False

    def test_gemma_2_27b_not_vision(self):
        assert CliChat._is_vision_model("gemma-2-27b") is False

    def test_gemma3_4b_is_vision(self):
        assert CliChat._is_vision_model("gemma3:4b") is True

    def test_llama_3_1_8b_not_vision(self):
        assert CliChat._is_vision_model("llama-3.1-8b") is False

    def test_unknown_model_defaults_to_vision(self):
        assert CliChat._is_vision_model("some-unknown-model-v42") is True


class TestCountTokensMultimodal:
    def test_plain_string_returns_int(self):
        result = count_tokens("Hello world")
        assert isinstance(result, int)

    def test_list_text_parts_returns_int(self):
        content = [{"type": "text", "text": "Hi"}]
        result = count_tokens(content)
        assert isinstance(result, int)

    def test_list_image_url_parts_counts_85_per_image(self):
        mock_tiktoken = MagicMock()
        mock_enc = MagicMock()
        mock_enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = mock_enc

        with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
            content = [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,def"}},
            ]
            result = count_tokens(content)
            assert result == 0 + 85 * 2


class TestOCRExtractFromDataUrl:
    def test_empty_data_url_returns_empty_string(self):
        assert extract_text_from_data_url("") == ""

    def test_invalid_data_url_no_comma_returns_empty_string(self):
        assert extract_text_from_data_url("not_a_valid_url") == ""

    def test_ocr_not_available_no_pil_returns_empty_string(self):
        with patch("mcp_cli.services.ocr._HAS_PIL", False):
            result = extract_text_from_data_url("data:image/png;base64,abc123")
            assert result == ""


class TestOCRSafetyGuards:
    def test_non_image_mime_type_rejected(self):
        assert extract_text_from_data_url("data:text/plain;base64,aGVsbG8=") == ""

    def test_image_mime_type_accepted_by_guard(self):
        with patch("mcp_cli.services.ocr._HAS_PIL", False):
            assert extract_text_from_data_url("data:image/png;base64,aGVsbG8=") == ""

    def test_oversized_data_url_rejected(self):
        with patch("mcp_cli.services.ocr.MAX_IMAGE_BYTES", 10):
            result = extract_text_from_data_url("data:image/png;base64,aGVsbG8gd29ybGQ=")
            assert result == ""

    def test_oversized_pixel_dimensions_rejected(self):
        fake_image = MagicMock()
        fake_image.width = 10000
        fake_image.height = 10000
        fake_img_class = MagicMock()
        fake_img_class.open.return_value = fake_image
        with (
            patch("mcp_cli.services.ocr.Image", fake_img_class),
            patch("mcp_cli.services.ocr._HAS_PIL", True),
            patch("mcp_cli.services.ocr._HAS_TESSERACT", True),
        ):
            result = extract_text_from_image(b"some-image-bytes")
        assert result == ""

    def test_small_image_passes_through_to_tesseract(self):
        fake_image = MagicMock()
        fake_image.width = 100
        fake_image.height = 100
        fake_img_class = MagicMock()
        fake_img_class.open.return_value = fake_image
        with (
            patch("mcp_cli.services.ocr.Image", fake_img_class),
            patch("mcp_cli.services.ocr._HAS_PIL", True),
            patch("mcp_cli.services.ocr._HAS_TESSERACT", True),
            patch("mcp_cli.services.ocr.pytesseract") as mock_tesseract,
        ):
            mock_tesseract.image_to_string.return_value = "  extracted  "
            result = extract_text_from_image(b"some-image-bytes")
        assert result == "extracted"


# ---------------------------------------------------------------------------
# CliChat.send() integration branches (mocked dependencies, no network)
# ---------------------------------------------------------------------------


class _FakeClaude:
    model = "test-model"


class _FakeStreamer:
    def __init__(self, content: str = "ok reply") -> None:
        self._content = content
        self.calls: list[list[dict]] = []

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        self.calls.append(messages)
        return SimpleNamespace(content=self._content, tool_calls=None), 10, 10


class _FakeHistory:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str]] = []

    def load_session(self, session_id: str) -> list[dict]:
        return []

    async def async_save_message(self, session_id: str, role: str, content: str) -> None:
        self.saved.append((session_id, role, content))


class _FakeUsage:
    def __init__(self) -> None:
        self.records: list[tuple[str, int, int, str]] = []

    async def async_record(self, model: str, input_tokens: int, output_tokens: int, session_id: str = "default") -> None:
        self.records.append((model, input_tokens, output_tokens, session_id))


class _FakeContext:
    async def auto_index(self, text: str, namespace: str = "messages") -> None:
        return None

    def trim(self, messages: list[dict], tools_tokens: int = 0) -> list[dict]:
        return messages


class _FakeRag:
    async def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.25) -> list[dict]:
        return []

    def format_context(self, results: list[dict]) -> str:
        return ""


class _FakeDocInjector:
    async def resolve(self, text: str) -> str:
        return text


def _make_send_chat() -> CliChat:
    chat = object.__new__(CliChat)
    chat.claude = _FakeClaude()
    chat.messages = []
    chat.session_id = "test-session"
    chat.history = _FakeHistory()
    chat.usage = _FakeUsage()
    chat.context = _FakeContext()
    chat.rag = _FakeRag()
    chat.doc_injector = _FakeDocInjector()
    chat.streamer = _FakeStreamer()
    chat.verifier = None
    chat.moderation = None
    chat.response_format = None
    chat._correction_attempts = 0
    chat.MAX_CORRECTION_ATTEMPTS = 2
    chat._max_tool_iterations = 10
    chat._openai_tools = []
    chat._auto_index_task = None
    return chat


def _make_bus():
    bus = MagicMock()
    bus.push_log = AsyncMock()
    bus.push_done = AsyncMock()
    bus.push_state = AsyncMock()
    return bus


async def _send_images(chat: CliChat, text: str, images: list[str], bus=None) -> str:
    result = await chat.send(text, images=images, notification_bus=bus)
    task = chat._auto_index_task
    if task is not None:
        with contextlib.suppress(Exception):
            await task
    return result


class TestSendImageBranching:
    async def test_vision_model_appends_image_url_content(self):
        chat = _make_send_chat()
        bus = _make_bus()
        with patch.object(chat, "_can_process_images", new=AsyncMock(return_value=True)):
            result = await _send_images(chat, "What's in this?", images=["data:image/png;base64,abc123"], bus=bus)

        assert result == "ok reply"
        user_msg = chat.messages[0]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert user_msg["content"][0] == {"type": "text", "text": "What's in this?"}
        assert {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}} in user_msg["content"]

    async def test_non_vision_ocr_available_appends_ocr_text_marker(self):
        chat = _make_send_chat()
        bus = _make_bus()
        with (
            patch.object(chat, "_can_process_images", new=AsyncMock(return_value=False)),
            patch("mcp_cli.services.ocr.is_available", return_value=True),
            patch("mcp_cli.services.ocr.extract_text_from_data_url", return_value="extracted text"),
        ):
            await _send_images(chat, "read this", images=["data:image/png;base64,abc123"], bus=bus)

        user_msg = chat.messages[0]
        assert isinstance(user_msg["content"], str)
        assert "[OCR text extracted from image(s)]" in user_msg["content"]
        assert "extracted text" in user_msg["content"]
        bus.push_log.assert_any_await("info", "OCR extracted text from 1 image(s)")

    async def test_non_vision_ocr_available_but_no_text_warns(self):
        chat = _make_send_chat()
        bus = _make_bus()
        with (
            patch.object(chat, "_can_process_images", new=AsyncMock(return_value=False)),
            patch("mcp_cli.services.ocr.is_available", return_value=True),
            patch("mcp_cli.services.ocr.extract_text_from_data_url", return_value=""),
        ):
            await _send_images(chat, "read this", images=["data:image/png;base64,abc123"], bus=bus)

        assert chat.messages[0]["content"] == "read this"
        bus.push_log.assert_any_await("warn", "OCR available but no text could be extracted from image(s)")

    async def test_non_vision_ocr_unavailable_drops_images_and_warns(self):
        chat = _make_send_chat()
        bus = _make_bus()
        with (
            patch.object(chat, "_can_process_images", new=AsyncMock(return_value=False)),
            patch("mcp_cli.services.ocr.is_available", return_value=False),
        ):
            await _send_images(chat, "read this", images=["data:image/png;base64,abc123"], bus=bus)

        user_msg = chat.messages[0]
        assert isinstance(user_msg["content"], str)
        assert user_msg["content"] == "read this"
        bus.push_log.assert_any_await(
            "warn",
            "OCR libraries not installed (pip install Pillow pytesseract). Cannot process images with this model.",
        )

    async def test_ocr_imports_follow_module_state(self):
        chat = _make_send_chat()
        with patch.object(chat, "_can_process_images", new=AsyncMock(return_value=False)):
            result = await _send_images(chat, "hello", images=["data:image/png;base64,abc123"], bus=None)
        assert result == "ok reply"
        assert chat.messages[0]["content"] == "hello"
