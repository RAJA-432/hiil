from __future__ import annotations

import re
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)


def chunk_by_tokens(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
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
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def extract_text_from_docx(content: bytes) -> str:
    from docx import Document
    import io
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
