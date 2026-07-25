"""
Streamlit chat UI — runs standalone or behind the vajram FastAPI gateway.

Standalone:
    streamlit run my_streamlit_app.py

Behind gateway:
    uvicorn vajram:app --port 8000
"""

from __future__ import annotations

import json
import os

import httpx
import streamlit as st

API_BASE = os.getenv("VAJRAM_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="hiil", layout="wide")
st.title("hiil")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize file upload state
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []


def api_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def upload_files_to_api(files) -> list[dict]:
    """Upload files to the API and return document IDs."""
    results = []
    for uploaded_file in files:
        try:
            # Upload to /api/upload endpoint
            file_bytes = uploaded_file.read()
            resp = httpx.post(
                f"{API_BASE}/api/upload",
                files={"file": (uploaded_file.name, file_bytes)},
                timeout=30,
            )
            if resp.is_success:
                data = resp.json()
                results.append({
                    "doc_id": data.get("doc_id"),
                    "filename": data.get("filename", uploaded_file.name),
                    "size": len(file_bytes)
                })
            else:
                st.error(f"Failed to upload {uploaded_file.name}: {resp.status_code}")
        except Exception as e:
            st.error(f"Error uploading {uploaded_file.name}: {e}")
    return results


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Status")

    try:
        resp = httpx.get(f"{API_BASE}/api/status", headers=api_headers(), timeout=5)
        if resp.is_success:
            s = resp.json()
            st.json(s)
    except Exception:
        st.caption("Status unavailable")

    st.divider()
    st.subheader("Sessions")
    try:
        resp = httpx.get(f"{API_BASE}/api/sessions", headers=api_headers(), timeout=5)
        if resp.is_success:
            sessions = resp.json().get("sessions", [])
            selected = st.selectbox("Switch session", sessions or ["(none)"])
            if selected and selected != "(none)":
                httpx.post(
                    f"{API_BASE}/api/session/switch",
                    headers=api_headers(),
                    json={"session_id": selected},
                    timeout=5,
                )
                st.session_state.messages = []
                st.rerun()
    except Exception:
        pass

    st.divider()
    st.subheader("File Upload")
    uploaded_files = st.file_uploader(
        "Upload documents for context",
        accept_multiple_files=True,
        help="Upload PDFs, docs, or text files to provide context to the model"
    )

    if uploaded_files:
        st.write(f"Selected {len(uploaded_files)} file(s):")
        for uploaded_file in uploaded_files:
            st.write(f"- {uploaded_file.name} ({uploaded_file.size} bytes)")

        if st.button("Upload Files"):
            with st.spinner("Uploading files..."):
                results = upload_files_to_api(uploaded_files)
                if results:
                    st.session_state.uploaded_files.extend(results)
                    st.success(f"Uploaded {len(results)} file(s)")
                    st.rerun()

    # Show uploaded files
    if st.session_state.uploaded_files:
        st.write("**Uploaded Files:**")
        for f in st.session_state.uploaded_files:
            st.write(f"- {f['filename']} (ID: {f['doc_id'][:8]}...)")

        if st.button("Clear Uploaded Files"):
            st.session_state.uploaded_files = []
            st.rerun()

    if st.button("New session"):
        httpx.post(f"{API_BASE}/api/session/new", headers=api_headers(), timeout=5)
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Type a message..."):
    # Include uploaded file context in the message
    context_parts = []
    if st.session_state.uploaded_files:
        context_parts.append("Document context:")
        for f in st.session_state.uploaded_files:
            context_parts.append(f"@@{f['doc_id']} ({f['filename']})")
        context_parts.append("---")

    message_with_context = prompt
    if context_parts:
        message_with_context = "\n".join(context_parts) + "\n\n" + prompt

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{API_BASE}/api/chat?stream=1",
                    headers={**api_headers(), "Accept": "text/event-stream"},
                    json={"message": message_with_context},
                )
                if resp.is_success:
                    for line in resp.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if data.get("type") == "tokens":
                                full = data["text"]
                                placeholder.markdown(full + "▌")
                            elif data.get("type") == "tools":
                                st.caption(f"→ used {data.get('count', 0)} tool(s)")
                        except json.JSONDecodeError:
                            continue
                    placeholder.markdown(full)
                else:
                    st.error(f"API error: {resp.status_code}")
        except httpx.HTTPError as e:
            st.error(f"Connection error: {e}")

    if full:
        st.session_state.messages.append({"role": "assistant", "content": full})
