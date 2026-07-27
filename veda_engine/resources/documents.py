from __future__ import annotations

import os

from veda_engine.storage.store import get_document, list_document_ids


def _get_user() -> str:
    return os.environ.get("HIIL_USER_ID", "default")


def list_docs() -> list[str]:
    """List all available document IDs."""
    return list_document_ids(user_id=_get_user())


def fetch_doc(doc_id: str) -> str:
    """Fetch the raw text of a specific document."""
    return get_document(doc_id, user_id=_get_user())
