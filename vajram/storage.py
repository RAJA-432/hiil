"""File storage integration for vajram."""
from __future__ import annotations

import uuid
from pathlib import Path

from mcp_server.storage.store import (
    create_document,
    get_document,
    list_document_info,
)

# Directory for storing raw file content
FILES_DIR = Path(__file__).parent.parent / "storage_files"
FILES_DIR.mkdir(exist_ok=True)


class HspStorage:
    """Handles file uploads and document storage integration."""

    async def store_file(self, file_data: bytes, filename: str) -> str:
        """Store a file and return its document ID."""
        doc_id = str(uuid.uuid4())

        # Save raw file content
        file_path = FILES_DIR / doc_id
        file_path.write_bytes(file_data)

        # Store document metadata in document store
        create_document(doc_id, f"[File: {filename}]")

        return doc_id

    async def get_file_content(self, doc_id: str) -> bytes | None:
        """Retrieve stored file content."""
        file_path = FILES_DIR / doc_id
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def list_documents(self) -> list[dict]:
        """List all stored documents with metadata."""
        return list_document_info()

    def get_document(self, doc_id: str) -> str:
        """Get document content by ID."""
        return get_document(doc_id)
