# Production Hardening — Summary

## Lighthouse (mobile, throttled)
- **Performance**: 80/100 (FCP 1.5s, LCP 2.5s, TBT 0ms, CLS 0, SI 1.5s)
- **Accessibility**: 91/100
- **Best Practices**: 96/100
- **SEO**: 100/100

Scan predates latest rebuild — expect improvements on icon 404, contrast, cache TTL, compression.

## Fixes Deployed & Verified

| Fix | File(s) | Status |
|-----|---------|--------|
| GZip compression (`minimum_size=500`) | `vajra_gate/__init__.py:48` | ✅ `content-encoding: gzip` on CSS & HTML |
| Cache headers (1 year immutable) on `/canvas/assets/` | `vajra_gate/__init__.py:86-93` | ✅ `cache-control: public, max-age=31536000, immutable` |
| Manifest → `/canvas/manifest.json` | `index.html`, `public/manifest.json`, `sw.js` | ✅ Correct paths, icon 404 fixed |
| Icon paths in manifest → `/canvas/icon-*.svg` | `public/manifest.json` | ✅ `/canvas/icon-192.svg` + `/canvas/icon-512.svg` returning 200 |
| Contrast: `--text-muted` #666→#999, `--text-dim` #444→#888 | `src/styles/base.css` | ✅ Built CSS confirms `#999`/`#888` (dark), `#555`/`#555` (light) |
| Markdown lazy-loaded via dynamic `import()` | `MarkdownRenderer.jsx` | ✅ 339 kB vendor-markdown chunk off critical path |
| `App.jsx` refactor 317→80 lines | `context/ChatContext.jsx`, `context/UIContext.jsx`, `hooks/useAppState.js` | ✅ Code quality |
| Confirm dialog + undo snackbar | `ConfirmDialog.jsx` | ✅ Phase 2 |
| Search endpoint + panel | `routers/search.py`, `SearchPanel.jsx` | ✅ Phase 3 |
| Mobile hamburger nav | `Sidebar.jsx`, `App.jsx` | ✅ Phase 3 |
| Pagination (`limit`/`offset`) | `routers/sessions.py`, `services/history.py` | ✅ Phase 3 |
| Loading skeletons, error states, connectivity indicator | Various | ✅ Phase 1 |
| HTML meta/OG/PWA tags, anti-FOUC, splash, noscript, ARIA, print/reduced-motion/forced-colors | `index.html` | ✅ |
| `manualChunks` splitting (vendor-react, vendor-markdown) | `vite.config.js` | ✅ |
| Tests (18 across 5 files) | Vitest + jsdom | ✅ |
| Backend: doc warning→debug, `COUNT(*)` + `LIMIT/OFFSET` | `server_manager.py`, `history.py` | ✅ |

## Remaining Issues

1. **Select without `aria-label`** — Model picker `<select>` fails Lighthouse `select-name` audit
2. **New conversation button contrast** — `#4a9eff` on `#2a5a8a` (2.6:1, fails 3:1/4.5:1)
3. **Render-blocking CSS** — 44 kB CSS blocks ~630ms; consider inlining critical CSS or `<link rel="preload">`
4. **Unused JS** — vendor-markdown 339 kB (77% unused), main 252 kB (42% unused) — mitigated by lazy loading
5. **Port 8000 zombie** — Old process holds port 8000; server running on 8001 instead
