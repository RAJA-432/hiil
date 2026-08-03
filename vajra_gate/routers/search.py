from fastapi import APIRouter, Depends, Query, Request

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat
from vajra_gate.models import SearchResponse, SearchResultItem

router = APIRouter()


@router.get("/api/search", response_model=SearchResponse)
async def search_messages(
    request: Request,
    q: str = Query(..., min_length=1),
    user: str = Depends(get_current_user),
):
    chat = await _require_chat(request)
    raw = await chat.history.async_global_search(q, limit=50)

    session_ids = list({r["session_id"] for r in raw})
    summaries = {
        s["session_id"]: s
        for s in await chat.history.async_session_summaries_for(session_ids)
    }
    titles = {}
    for sid in session_ids:
        meta = summaries.get(sid)
        titles[sid] = ((meta["title"] if meta else "") or sid)[:80]

    results = []
    for r in raw:
        content = r["content"]
        snippet = content[:200]
        results.append(SearchResultItem(
            conversation_id=r["session_id"],
            conversation_title=titles.get(r["session_id"], r["session_id"]),
            message_id=r["id"],
            content=content,
            snippet=snippet,
            timestamp=r["timestamp"],
        ))

    return SearchResponse(results=results, total_count=len(results))
