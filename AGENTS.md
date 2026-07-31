# Project State

## Completed

| Work | Files | Status |
|------|-------|--------|
| **Auto-create conversation** — Chat now creates a conversation when user sends first message | `useChat.js`, `ChatContext.jsx` | ✅ |
| **Vision/image pipeline** — Images paste/drag-drop → multimodal content array for vision models, OCR fallback for non-vision models | `mcp_cli/services/chat.py`, `ocr.py`, `usage.py`, `context_manager.py`, `factory.py`; `vajra_gate/models.py`, `chat.py`, `routers/chat.py`; `api/chat.js`, `hooks/useChat.js` | ✅ 15 backend + 3 frontend tests |
| GZip compression (`minimum_size=500`) | `vajra_gate/__init__.py:48` | ✅ |
| Cache headers (1 year immutable) on `/canvas/assets/` | `vajra_gate/__init__.py:86-93` | ✅ |
| Manifest → `/canvas/manifest.json` | `index.html`, `public/manifest.json`, `sw.js` | ✅ |
| Icon paths in manifest → `/canvas/icon-*.svg` | `public/manifest.json` | ✅ |
| Contrast: `--text-muted` #666→#999, `--text-dim` #444→#888 | `src/styles/base.css` | ✅ |
| Markdown lazy-loaded via dynamic `import()` | `MarkdownRenderer.jsx` | ✅ |
| `App.jsx` refactor 317→80 lines | `context/ChatContext.jsx`, `context/UIContext.jsx`, `hooks/useAppState.js` | ✅ |
| Confirm dialog + undo snackbar | `ConfirmDialog.jsx` | ✅ |
| Search endpoint + panel | `routers/search.py`, `SearchPanel.jsx` | ✅ |
| Mobile hamburger nav | `Sidebar.jsx`, `App.jsx` | ✅ |
| Pagination (`limit`/`offset`) | `routers/sessions.py`, `services/history.py` | ✅ |
| Loading skeletons, error states, connectivity indicator | Various | ✅ |
| HTML meta/OG/PWA tags, anti-FOUC, splash, noscript, ARIA, print/reduced-motion/forced-colors | `index.html` | ✅ |
| `manualChunks` splitting (vendor-react, vendor-markdown) | `vite.config.js` | ✅ |
| Tests (84 backend + 26 frontend) | Vitest + pytest | ✅ |
| Backend: doc warning→debug, `COUNT(*)` + `LIMIT/OFFSET` | `server_manager.py`, `history.py` | ✅ |

## Remaining Issues

1. **Select without `aria-label`** — Model picker `<select>` fails Lighthouse `select-name` audit
2. **New conversation button contrast** — `#4a9eff` on `#2a5a8a` (2.6:1, fails 3:1/4.5:1)
3. **Render-blocking CSS** — 44 kB CSS blocks ~630ms; consider inlining critical CSS or `<link rel="preload">`
4. **Unused JS** — vendor-markdown 339 kB (77% unused), main 252 kB (42% unused) — mitigated by lazy loading
