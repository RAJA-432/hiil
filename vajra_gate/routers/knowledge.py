from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat
from vajra_gate.models import (
    DocumentDetailResponse,
    DocumentListResponse,
    KnowledgeListResponse,
    RetrieveRequest,
    RetrieveResponse,
    UploadResponse,
)
from vajra_gate.storage import HspStorage

router = APIRouter()
storage = HspStorage()


@router.post("/api/upload", response_model=UploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...), user: str = Depends(get_current_user)):
    try:
        file_data = await file.read()
        filename = file.filename or "unknown"
        doc_id = await storage.store_file(file_data, filename, user_id=user)

        result: dict[str, Any] = {"doc_id": doc_id, "filename": filename}

        chat = await _require_chat(request)
        rag_result = await chat.rag.index_document(file_data, filename)
        result["rag"] = rag_result

        return UploadResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(user: str = Depends(get_current_user)):
    docs = storage.list_documents(user_id=user)
    return DocumentListResponse(documents=docs)


@router.get("/api/documents/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(doc_id: str, user: str = Depends(get_current_user)):
    try:
        content = storage.get_document(doc_id, user_id=user)
        file_content = await storage.get_file_content(doc_id)
        return DocumentDetailResponse(
            doc_id=doc_id,
            content=content,
            has_file=file_content is not None,
            file_size=len(file_content) if file_content else 0,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/retrieve", response_model=RetrieveResponse)
async def retrieve_knowledge(request: Request, body: RetrieveRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    if not body.query:
        raise HTTPException(status_code=400, detail="query is required")
    results = await chat.rag.retrieve(body.query, top_k=body.top_k, min_score=body.min_score)
    return RetrieveResponse(results=results, count=len(results))


@router.get("/api/knowledge", response_model=KnowledgeListResponse)
async def list_knowledge(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    docs = await chat.rag.list_documents()
    return KnowledgeListResponse(documents=docs, count=len(docs))
