from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat
from vajra_gate.storage import HspStorage

router = APIRouter()
storage = HspStorage()


@router.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...), user: str = Depends(get_current_user)):
    """Upload a file, store it, and index it into the RAG knowledge base."""
    try:
        file_data = await file.read()
        filename = file.filename or "unknown"
        doc_id = await storage.store_file(file_data, filename, user_id=user)

        result: dict[str, Any] = {"doc_id": doc_id, "filename": filename}

        chat = await _require_chat(request)
        rag_result = await chat.rag.index_document(file_data, filename)
        result["rag"] = rag_result

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents")
async def list_documents(user: str = Depends(get_current_user)):
    """List all stored documents."""
    return {"documents": storage.list_documents(user_id=user)}


@router.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, user: str = Depends(get_current_user)):
    """Get document content by ID."""
    try:
        content = storage.get_document(doc_id, user_id=user)
        file_content = await storage.get_file_content(doc_id)
        return {
            "doc_id": doc_id,
            "content": content,
            "has_file": file_content is not None,
            "file_size": len(file_content) if file_content else 0
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/retrieve")
async def retrieve_knowledge(request: Request, user: str = Depends(get_current_user)):
    """Query the RAG knowledge base for relevant document chunks."""
    chat = await _require_chat(request)
    body = await request.json()
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    top_k = body.get("top_k", 5)
    min_score = body.get("min_score", 0.0)
    results = await chat.rag.retrieve(query, top_k=top_k, min_score=min_score)
    return {"results": results, "count": len(results)}


@router.get("/api/knowledge")
async def list_knowledge(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    docs = await chat.rag.list_documents()
    return {"documents": docs, "count": len(docs)}
