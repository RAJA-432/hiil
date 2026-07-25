from __future__ import annotations

from mcp_server.storage.store import get_document, list_document_ids


def list_docs() -> list[str]:
    """List all available document IDs."""
    return list_document_ids()


def fetch_doc(doc_id: str) -> str:
    """Fetch the raw text of a specific document."""
    return get_document(doc_id)
