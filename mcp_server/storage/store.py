from __future__ import annotations

import json
from pathlib import Path

STORE_FILE = Path(__file__).parent / "documents_store.json"

docs: dict[str, str] = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}

def _load_store():
    global docs
    if STORE_FILE.exists():
        try:
            docs.update(json.loads(STORE_FILE.read_text("utf-8")))
        except Exception:
            pass

def _save_store():
    STORE_FILE.write_text(json.dumps(docs, indent=2), encoding="utf-8")

_load_store()


def get_document(doc_id: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Document {doc_id} not found")
    return docs[doc_id]


def edit_document(doc_id: str, old_str: str, new_str: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Document {doc_id} not found")
    if old_str not in docs[doc_id]:
        raise ValueError(f"'{old_str}' not found in document {doc_id}")
    docs[doc_id] = docs[doc_id].replace(old_str, new_str)
    _save_store()
    return docs[doc_id]


def list_document_ids() -> list[str]:
    return list(docs.keys())

def create_document(doc_id: str, content: str) -> str:
    """Create a new document or update existing"""
    docs[doc_id] = content
    _save_store()
    return docs[doc_id]

def get_document_info(doc_id: str) -> dict:
    """Get document info including filename and size"""
    if doc_id not in docs:
        raise ValueError(f"Document {doc_id} not found")
    # Extract filename from doc_id (simple case)
    filename = doc_id.split('/')[-1] if '/' in doc_id else doc_id
    return {
        "id": doc_id,
        "filename": filename,
        "content": docs[doc_id]
    }

def list_document_info() -> list[dict]:
    """List all documents with their metadata"""
    return [get_document_info(doc_id) for doc_id in list_document_ids()]
