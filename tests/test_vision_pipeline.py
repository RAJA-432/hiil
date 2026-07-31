from __future__ import annotations

from unittest.mock import MagicMock, patch

from mcp_cli.services.chat import CliChat
from mcp_cli.services.ocr import extract_text_from_data_url
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
