from __future__ import annotations

import json
import os
import time

import httpx
import streamlit as st

API_BASE = os.getenv("VAJRAM_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="hiil", layout="wide", page_icon="⚡")
st.title("⚡ hiil")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "tool_logs" not in st.session_state:
    st.session_state.tool_logs = []


def api_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def upload_files_to_api(files) -> list[dict]:
    results = []
    for uploaded_file in files:
        try:
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
                    "size": len(file_bytes),
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
    st.subheader("🔌 System Status")
    try:
        resp = httpx.get(f"{API_BASE}/api/status", headers=api_headers(), timeout=5)
        if resp.is_success:
            s = resp.json()
            cols = st.columns(3)
            server_ok = isinstance(s.get("servers"), list) and len(s["servers"]) > 0
            cols[0].metric("Gateway", "🟢" if server_ok else "🔴")
            cols[1].metric("MCP", f"{len(s.get('servers', []))} servers")
            cols[2].metric("Model", s.get("model", "?")[:12])
            st.caption(f"Session: {s.get('session', '?')[:16]} · {s.get('messages', 0)} msgs")
    except Exception:
        st.error("🔴 Status unavailable")

    st.divider()
    st.subheader("💰 Usage")
    try:
        uresp = httpx.get(f"{API_BASE}/api/usage", headers=api_headers(), timeout=5)
        if uresp.is_success:
            u = uresp.json()
            sess = u.get("session", {})
            col1, col2, col3 = st.columns(3)
            col1.metric("Tokens", sess.get("total_tokens", 0))
            col2.metric("Cost", f"${sess.get('cost', 0):.6f}")
            col3.metric("Model", s.get("model", "?")[:10] if resp.is_success else "?")
    except Exception:
        st.caption("Usage data unavailable")

    st.divider()
    st.subheader("🎯 Model")
    try:
        mresp = httpx.get(f"{API_BASE}/api/models", headers=api_headers(), timeout=5)
        if mresp.is_success:
            models_data = mresp.json()
            models = models_data.get("models", [])
            active = models_data.get("active", "")
            if models:
                selected = st.selectbox(
                    "Switch model",
                    models,
                    index=models.index(active) if active in models else 0,
                    key="model_selector",
                )
                if selected and selected != active:
                    httpx.post(
                        f"{API_BASE}/api/model",
                        headers=api_headers(),
                        json={"model": selected},
                        timeout=5,
                    )
                    st.rerun()
    except Exception:
        st.caption("Model list unavailable")

    st.divider()
    st.subheader("📁 Sessions")
    try:
        sresp = httpx.get(f"{API_BASE}/api/sessions", headers=api_headers(), timeout=5)
        if sresp.is_success:
            sessions_data = sresp.json()
            sessions = sessions_data.get("sessions", [])
            active_sid = sessions_data.get("active", "")

            # Rename inline
            rename_target = st.selectbox(
                "Rename session",
                [""] + sessions,
                format_func=lambda x: f"✏️ {x[:24]}" if x else "— select —",
                key="rename_select",
            )
            if rename_target:
                new_name = st.text_input("New name", key="rename_input")
                if new_name and st.button("Rename"):
                    httpx.post(
                        f"{API_BASE}/api/session/rename",
                        headers=api_headers(),
                        json={"old_id": rename_target, "new_id": new_name},
                        timeout=5,
                    )
                    st.rerun()

            # Switch
            selected = st.selectbox(
                "Switch session",
                sessions or ["(none)"],
                index=sessions.index(active_sid) if active_sid in sessions else 0,
                key="session_switch",
            )
            if selected and selected != "(none)" and selected != active_sid:
                httpx.post(
                    f"{API_BASE}/api/session/switch",
                    headers=api_headers(),
                    json={"session_id": selected},
                    timeout=5,
                )
                st.session_state.messages = []
                st.rerun()

            # Delete
            del_target = st.selectbox(
                "Delete session",
                [""] + sessions,
                format_func=lambda x: f"🗑️ {x[:24]}" if x else "— select —",
                key="delete_select",
            )
            if del_target and st.button("Delete", type="secondary"):
                httpx.post(
                    f"{API_BASE}/api/session/delete",
                    headers=api_headers(),
                    json={"session_id": del_target},
                    timeout=5,
                )
                if del_target == active_sid:
                    st.session_state.messages = []
                st.rerun()
    except Exception:
        st.caption("Sessions unavailable")

    if st.button("➕ New session"):
        httpx.post(f"{API_BASE}/api/session/new", headers=api_headers(), timeout=5)
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("📎 File Upload")
    uploaded_files = st.file_uploader(
        "Upload documents for context",
        accept_multiple_files=True,
        help="Upload PDFs, docs, or text files to provide context to the model",
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

    if st.session_state.uploaded_files:
        st.write("**Uploaded Files:**")
        for i, f in enumerate(st.session_state.uploaded_files):
            cols = st.columns([4, 1])
            cols[0].write(f"📄 {f['filename']} (`{f['doc_id'][:8]}...`)")
            if cols[1].button("✕", key=f"rm_file_{i}"):
                st.session_state.uploaded_files.pop(i)
                st.rerun()

        if st.button("Clear All"):
            st.session_state.uploaded_files = []
            st.rerun()

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

for m in st.session_state.messages:
    avatar = "🤖" if m["role"] == "assistant" else "👤"
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])
        tool_logs = m.get("tool_logs", [])
        if tool_logs:
            with st.expander("🔧 Tool calls", expanded=False):
                for tl in tool_logs:
                    st.code(f"  {tl['tool']}({json.dumps(tl['args'], indent=2)[:200]})", language="json")
                    if tl.get("result"):
                        with st.expander("Result", expanded=False):
                            st.text(tl["result"][:500])

if prompt := st.chat_input("Type a message..."):
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
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    tool_logs: list[dict] = []
    tool_status = st.empty()
    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        tool_expander = st.expander("🔧 Live tool calls", expanded=True)
        tool_container = tool_expander.container()
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
                            evt_type = data.get("type")

                            if evt_type == "tokens":
                                full = data["text"]
                                placeholder.markdown(full + "▌")

                            elif evt_type == "tool_event":
                                tool_name = data.get("tool", "?")
                                args = data.get("args", {})
                                status = data.get("status", "")
                                result = data.get("result", "")

                                if status == "running":
                                    tool_status.info(f"🔧 **{tool_name}**({json.dumps(args)[:80]}...)")
                                elif status == "done":
                                    tool_status.empty()
                                    tool_logs.append({
                                        "tool": tool_name,
                                        "args": args,
                                        "result": result,
                                    })
                                    with tool_container:
                                        st.code(f"✅ {tool_name}({json.dumps(args)[:200]})")
                                        if result:
                                            with st.expander("Result", expanded=False):
                                                st.text(result[:500])
                                            st.divider()

                        except json.JSONDecodeError:
                            continue
                    placeholder.markdown(full)
                    tool_expander.expanded = False
                else:
                    st.error(f"API error: {resp.status_code}")
        except httpx.HTTPError as e:
            st.error(f"Connection error: {e}")

    if full:
        st.session_state.messages.append({
            "role": "assistant",
            "content": full,
            "tool_logs": tool_logs,
        })