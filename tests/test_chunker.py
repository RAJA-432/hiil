from __future__ import annotations

from mcp_cli.services.chunker import (
    chunk_by_content,
    chunk_by_tokens,
    detect_content_type,
    suggest_chunk_size,
)


class TestDetectContentType:
    def test_detects_python_code(self) -> None:
        text = (
            "def add(a, b):\n"
            "    return a + b\n\n"
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 42\n"
        )
        assert detect_content_type(text) == "code"

    def test_detects_prose(self) -> None:
        text = (
            "This is a plain document. It talks about things in ordinary "
            "sentences without any programming syntax. Just words and punctuation."
        )
        assert detect_content_type(text) == "text"

    def test_empty_text_is_text(self) -> None:
        assert detect_content_type("") == "text"

    def test_mixed_prose_with_code_keywords_stays_text(self) -> None:
        text = (
            "When a function is defined it can return a value. This paragraph "
            "happens to mention if, else, and for but is still prose."
        )
        assert detect_content_type(text) == "text"


class TestSuggestChunkSize:
    def test_code_gets_smaller_chunks(self) -> None:
        code = "def f():\n    return 1\n"
        assert suggest_chunk_size(code, default=512) == 256

    def test_code_respects_lower_bound(self) -> None:
        code = "def f():\n    return 1\n"
        assert suggest_chunk_size(code, default=100) == 100

    def test_prose_keeps_default(self) -> None:
        prose = "Just some ordinary sentences here for a plain document."
        assert suggest_chunk_size(prose, default=512) == 512


class TestChunkByContent:
    def test_code_chunks_are_smaller(self) -> None:
        code = "\n".join(f"def func_{i}():\n    return {i}\n" for i in range(200))
        chunks = chunk_by_content(code, default_size=512)
        assert chunks
        assert max(c["word_count"] for c in chunks) <= 256

    def test_prose_chunks_use_larger_default(self) -> None:
        prose = " ".join(f"word{i}" for i in range(2000))
        chunks = chunk_by_content(prose, default_size=512)
        assert chunks
        assert all(c["word_count"] <= 512 for c in chunks)

    def test_chunks_carry_content_type(self) -> None:
        code = "def f():\n    return 1\n"
        chunks = chunk_by_content(code)
        assert chunks
        assert all(c["content_type"] == "code" for c in chunks)

    def test_plain_text_chunks_marked_text(self) -> None:
        prose = " ".join(f"word{i}" for i in range(600))
        chunks = chunk_by_content(prose)
        assert chunks
        assert all(c["content_type"] == "text" for c in chunks)


class TestChunkByTokensCompat:
    def test_still_produces_overlapping_chunks(self) -> None:
        words = " ".join(f"w{i}" for i in range(300))
        chunks = chunk_by_tokens(words, chunk_size=100, overlap=20)
        assert chunks
        assert len(chunks) >= 3
        assert chunks[0]["word_count"] == 100
        # Overlap: next chunk starts 80 words in.
        assert chunks[1]["start_word"] == 80
