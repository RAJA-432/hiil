from __future__ import annotations

import re
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)

_CODE_KEYWORDS = {
    "async", "await", "bool", "break", "class", "const", "continue",
    "def", "elif", "else", "enum", "except", "False", "fn", "for",
    "from", "func", "function", "if", "import", "impl", "int", "lambda",
    "let", "namespace", "None", "null", "package", "print", "public",
    "pub", "private", "return", "str", "struct", "switch", "True",
    "try", "type", "var", "void", "while", "with", "yield",
}


def detect_content_type(text: str) -> str:
    """Return ``code`` or ``text`` based on lightweight heuristics."""
    lines = text.splitlines()
    scored = 0
    code_hits = 0
    for line in lines[:200]:
        stripped = line.strip()
        if not stripped:
            continue
        scored += 1
        if stripped.endswith((";", "{", "}")):
            code_hits += 1
        elif line[:1] in (" ", "\t") and line[1:2].strip():
            code_hits += 1
        elif stripped.split(" ", 1)[0] in _CODE_KEYWORDS:
            code_hits += 1
    if scored == 0:
        return "text"
    return "code" if code_hits / scored >= 0.15 else "text"


def suggest_chunk_size(text: str, default: int = 512) -> int:
    """Pick a chunk size that fits the content type.

    Code keeps smaller chunks so function/class boundaries stay dense enough
    for embeddings; prose can use larger windows.
    """
    if detect_content_type(text) == "code":
        return max(64, min(default, 256))
    return default


def chunk_by_content(
    text: str,
    default_size: int = 512,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    """Chunk ``text`` using a size adapted to its content type."""
    chunk_size = suggest_chunk_size(text, default=default_size)
    chunks = chunk_by_tokens(text, chunk_size=chunk_size, overlap=overlap)
    for chunk in chunks:
        chunk["content_type"] = detect_content_type(chunk["text"])
    return chunks


def chunk_by_tokens(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    words = text.split()
    if not words:
        return chunks

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append({
            "text": chunk_text,
            "start_word": start,
            "end_word": end,
            "word_count": end - start,
        })
        if end == len(words):
            break
        start += chunk_size - overlap

    return chunks


def chunk_by_sentences(
    text: str,
    max_chars: int = 1500,
    overlap_chars: int = 150,
) -> list[dict[str, Any]]:
    sentence_end = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_end.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []

    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)
        if current_len + sent_len > max_chars and current:
            chunk_text = " ".join(current)
            chunks.append({
                "text": chunk_text,
                "char_count": current_len,
                "sentence_count": len(current),
            })
            overlap_sents: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) > overlap_chars and overlap_sents:
                    break
                overlap_sents.insert(0, s)
                overlap_len += len(s)
            current = overlap_sents
            current_len = overlap_len

        current.append(sent)
        current_len += sent_len

    if current:
        chunk_text = " ".join(current)
        chunks.append({
            "text": chunk_text,
            "char_count": current_len,
            "sentence_count": len(current),
        })

    return chunks


def extract_text_from_pdf(content: bytes) -> str:
    import io

    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def extract_text_from_docx(content: bytes) -> str:
    import io

    from docx import Document
    doc = Document(io.BytesIO(content))
    paragraphs: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())
    return "\n\n".join(paragraphs)


def extract_text(content: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(content)
    elif lower.endswith(".docx"):
        return extract_text_from_docx(content)
    else:
        return content.decode("utf-8", errors="replace")
