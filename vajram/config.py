import os

from dotenv import load_dotenv

load_dotenv()

VAJRAM_LOG_LEVEL = os.getenv("VAJRAM_LOG_LEVEL", "CRITICAL").upper()
VAJRAM_PORT = int(os.getenv("VAJRAM_PORT", "8000"))
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://127.0.0.1:8501")
VAJRAM_NO_STREAMLIT = os.getenv("VAJRAM_NO_STREAMLIT", "").lower() in ("1", "true")
VAJRAM_CHAT_LOG = os.getenv("VAJRAM_CHAT_LOG", "")

_CHAT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>hiil</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:#000; color:#555; display:flex; height:100vh; }

/* ---- sidebar ---- */
#sidebar { width:240px; min-width:240px; background:#0a0a0a; border-right:1px solid #111;
           display:flex; flex-direction:column; }
#sidebar h2 { font-size:.85rem; color:#333; text-transform:uppercase; letter-spacing:.05em;
               padding:1rem 1rem .5rem; }
#sessions { flex:1; overflow-y:auto; padding:0 .5rem; }
.session-item { padding:.5rem .75rem; border-radius:6px; cursor:pointer; font-size:.875rem;
                 color:#444; transition:background .15s; white-space:nowrap; overflow:hidden;
                 text-overflow:ellipsis; }
.session-item:hover { background:#0f0f0f; }
.session-item.active { background:#002a2a; color:#666; }
#new-session { margin:.5rem; padding:.5rem; border-radius:6px; border:1px solid #111;
               background:#000; color:#444; cursor:pointer; font-size:.8rem; text-align:center; }
#new-session:hover { background:#0f0f0f; }

/* ---- main ---- */
#main { flex:1; display:flex; flex-direction:column; min-width:0; }
header { background:#0a0a0a; border-bottom:1px solid #111; padding:.75rem 1.5rem;
          display:flex; align-items:center; justify-content:space-between; }
header h1 { font-size:1.1rem; color:#444; }
#status { font-size:.8rem; color:#333; }
#status.thinking { color:#4a3a00; }
#messages { flex:1; overflow-y:auto; padding:1.5rem; display:flex; flex-direction:column; gap:.75rem; }
.msg { max-width:75%; padding:.75rem 1rem; border-radius:8px; line-height:1.5; white-space:pre-wrap;
       word-wrap:break-word; }
.msg.user { align-self:flex-end; background:#002a2a; color:#555; }
.msg.assistant { align-self:flex-start; background:#0a0a0a; border:1px solid #151515; color:#555; }

.msg code { background:#111; padding:.1em .3em; border-radius:4px; font-size:.875em; color:#555; }
.msg pre { background:#0a0a0a; padding:.75rem; border-radius:6px; overflow-x:auto; margin:.5rem 0;
           border:1px solid #151515; }
.msg pre code { background:none; padding:0; }

/* ---- input ---- */
.input-row { display:flex; gap:.5rem; padding:.75rem 1.5rem; background:#0a0a0a;
              border-top:1px solid #111; }
#input { flex:1; padding:.65rem .75rem; border-radius:6px; border:1px solid #111;
          background:#000; color:#555; font-size:.9rem; resize:none; max-height:150px; }
#input:focus { outline:2px solid #002a2a; border-color:transparent; }
#send { padding:.65rem 1.25rem; border-radius:6px; border:none; background:#002a2a;
        color:#555; font-weight:600; cursor:pointer; font-size:.9rem; }
#send:hover { background:#003a3a; }
#send:disabled { opacity:.5; cursor:not-allowed; }

/* ---- markdown rendering ---- */
.msg h1,.msg h2,.msg h3,.msg h4 { margin:.5rem 0 .25rem; color:#555; }
.msg h1 { font-size:1.2rem; } .msg h2 { font-size:1.1rem; } .msg h3 { font-size:1rem; }
.msg ul,.msg ol { padding-left:1.25rem; margin:.25rem 0; }
.msg li { margin:.15rem 0; }
.msg p { margin:.25rem 0; }
.msg a { color:#004a4a; }
.msg blockquote { border-left:3px solid #151515; padding-left:.75rem; margin:.5rem 0;
                  color:#333; }
.msg hr { border:none; border-top:1px solid #111; margin:.5rem 0; }
.msg table { border-collapse:collapse; margin:.5rem 0; font-size:.875rem; }
.msg th,.msg td { border:1px solid #151515; padding:.35rem .6rem; text-align:left; }
.msg th { background:#0a0a0a; color:#555; }

.typing-dots::after { content:""; animation:dots 1.5s steps(3,end) infinite; }
@keyframes dots { 0% { content:""; } 33% { content:"."; } 66% { content:".."; } 100% { content:"..."; } }
</style>
</head>
<body>

<!-- sidebar -->
<div id="sidebar">
  <h2>Sessions</h2>
  <div id="sessions"></div>
  <button id="new-session">+ New session</button>
</div>

<!-- main -->
<div id="main">
  <header>
    <h1>hiil</h1>
    <span id="status">connected</span>
  </header>
  <div id="messages"></div>
  <div class="input-row">
    <textarea id="input" rows="1" placeholder="Type a message..." autofocus></textarea>
    <button id="send">Send</button>
  </div>
</div>

<script>
const msgsDiv = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
const sessionsDiv = document.getElementById('sessions');
const newSessionBtn = document.getElementById('new-session');

let currentSession = 'default';

// auto-resize textarea
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 150) + 'px';
});

// ---- helpers ---- //

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function renderMarkdown(text) {
  let html = escapeHtml(text);
  // code blocks
  html = html.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
  // inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // images
  html = html.replace(/!\\[([^\\]]*)\\]\\(([^)]+)\\)/g, '<img src="$2" alt="$1" style="max-width:100%">');
  // links
  html = html.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // bold/italic
  html = html.replace(/\\*\\*\\*([^*]+)\\*\\*\\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
  html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
  // line breaks
  html = html.replace(/\\n/g, '<br>');
  return html;
}

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  if (role === 'assistant') {
    div.innerHTML = renderMarkdown(text);
  } else {
    div.textContent = text;
  }
  msgsDiv.appendChild(div);
  msgsDiv.scrollTop = msgsDiv.scrollHeight;
  return div;
}

// ---- sessions ---- //

async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    if (!res.ok) return;
    const data = await res.json();
    sessionsDiv.innerHTML = '';
    for (const sid of data.sessions || []) {
      const item = document.createElement('div');
      item.className = 'session-item' + (sid === currentSession ? ' active' : '');
      item.textContent = sid;
      item.addEventListener('click', () => switchSession(sid));
      sessionsDiv.appendChild(item);
    }
  } catch(e) {}
}

async function switchSession(sid) {
  if (sid === currentSession) return;
  try {
    await fetch('/api/session/switch', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sid}),
    });
    currentSession = sid;
    msgsDiv.innerHTML = '';
    await loadHistory();
    loadSessions();
  } catch(e) {}
}

async function loadHistory() {
  try {
    const res = await fetch('/api/history/' + encodeURIComponent(currentSession));
    if (!res.ok) return;
    const data = await res.json();
    for (const m of data.messages || []) {
      if (m.role === 'user' || m.role === 'assistant') {
        addMsg(m.role, m.content || '');
      }
    }
  } catch(e) {}
}

newSessionBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/session/new', {method: 'POST'});
    if (!res.ok) return;
    const data = await res.json();
    currentSession = data.session_id;
    msgsDiv.innerHTML = '';
    loadSessions();
    statusEl.textContent = 'connected';
  } catch(e) {}
});

// ---- send ---- //

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  addMsg('user', text);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;
  statusEl.textContent = 'thinking...';
  statusEl.className = 'thinking';

  const placeholder = addMsg('assistant', '');

  try {
    const res = await fetch('/api/chat?stream=1', {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'Accept':'text/event-stream'},
      body: JSON.stringify({message: text, session_id: currentSession}),
    });
    if (!res.ok) {
      placeholder.innerHTML = '<em>Error: ' + res.status + '</em>';
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          if (data.type === 'tokens') {
            fullText = data.text;
            placeholder.innerHTML = renderMarkdown(fullText) + '<span class="typing-dots"></span>';
          }
        } catch(e) {}
      }
    }
    if (fullText) {
      placeholder.innerHTML = renderMarkdown(fullText);
    } else if (!placeholder.textContent) {
      placeholder.innerHTML = '<em>(empty response)</em>';
    }
  } catch (e) {
    placeholder.innerHTML = '<em>Connection error</em>';
  } finally {
    sendBtn.disabled = false;
    statusEl.textContent = 'connected';
    statusEl.className = '';
  }
}

// ---- init ---- //

loadSessions();
</script>
</body>
</html>
"""
