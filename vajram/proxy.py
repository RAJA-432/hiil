import asyncio
import logging
from urllib.parse import urljoin

import httpx
import websockets
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

logger = logging.getLogger("vajram")

router = APIRouter()


@router.websocket("/_stcore/stream")
async def streamlit_ws_proxy(ws: WebSocket):
    await ws.accept()
    target = str(ws.app.state.streamlit_url).replace("http://", "ws://")
    try:
        async with websockets.connect(f"{target}/_stcore/stream") as backend:
            async def forward():
                try:
                    while True:
                        data = await backend.recv()
                        await ws.send_bytes(data) if isinstance(data, bytes) else await ws.send_text(data)
                except websockets.ConnectionClosed:
                    pass
            forward_task = asyncio.create_task(forward())
            try:
                while True:
                    data = await ws.receive()
                    if data["type"] == "websocket.receive":
                        msg = data.get("text") or data.get("bytes")
                        if msg is not None:
                            await backend.send(msg)
                    elif data["type"] == "websocket.disconnect":
                        break
            except WebSocketDisconnect:
                pass
            finally:
                forward_task.cancel()
                try:
                    await forward_task
                except (asyncio.CancelledError, Exception):
                    pass
    except websockets.InvalidURI as exc:
        logger.error("WebSocket proxy bad URI %s: %s", target, exc)
        await ws.close()
    except (OSError, websockets.WebSocketException) as exc:
        logger.warning("WebSocket proxy connection failed: %s", exc)
        try:
            await ws.close()
        except Exception:
            pass


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy(request: Request, path: str):
    target = urljoin(str(request.app.state.streamlit_url).rstrip("/") + "/", path)
    qs = request.url.query
    if qs:
        target += "?" + qs

    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("authorization", None)

    try:
        resp = await request.app.state.http_client.request(
            method=request.method,
            url=target,
            headers=headers,
            content=body or None,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
    except httpx.ConnectError:
        return HTMLResponse(
            "<h2>Streamlit backend unavailable</h2>"
            "<p>Start it manually: <code>streamlit run my_streamlit_app.py</code></p>",
            status_code=502,
        )
