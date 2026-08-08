# Drishti Engine — Consumer Search & Media

Image generation, stock-template search, flight search, healthcare lookup, and
local browser-history search. Real keyless APIs where available, with offline
mock fallbacks.

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `graphic_art` | `(prompt, width=1024, height=1024, style="") -> str` | Generate an image from a text prompt via Pollinations.ai (keyless); saved to `storage_files/media/`; SVG fallback on network failure. |
| `search_template_images` | `(query, limit=5) -> str` | Search stock/template images (Pexels if `HIIL_PEXELS_API_KEY`, else keyless Openverse; local catalog fallback). |
| `search_template_videos` | `(query, limit=5) -> str` | Search stock/template videos (Pexels if key set, else local catalog). |
| `search_flights` | `(origin, destination, date, passengers=1, cabin="economy", sort="price", limit=10) -> str` | Deterministic offline mock flight search; date `YYYY-MM-DD`; cabin economy/premium/business/first; sort price/duration/departure. |
| `search_airports` | `(query, limit=8) -> str` | Resolve IATA codes or city names from the built-in airport catalog. |
| `search_healthcare` | `(query, category=None, limit=5) -> str` | Curated educational health entries (conditions/symptoms/medications) with a disclaimer. |
| `browser_search` | `(query, limit=10, user_id="default") -> str` | Full-text search of the local per-user browsing history (title/domain/url/tags). |
| `browser_add` | `(title, url, tags="", user_id="default") -> str` | Record a page visit (write tool — gated at AgentConfig level). |

## Usage

- `search_airports("del")` → `[{iata: "DEL", name: "New Delhi", ...}]`
- `search_flights("DEL", "BOM", "2026-08-20")` → JSON with flights sorted by price
- `graphic_art("a minimalist workspace hero banner")` → saves PNG under `storage_files/media/`
- `search_template_images("team meeting")` → stock image URLs
- `search_healthcare("headache")` → educational entry + disclaimer
- `browser_search("arxiv")` → recent arXiv pages from local history

## Notes

- Generated artwork is written to `<workspace>/storage_files/media/`.
- Network tools validate target hosts against an SSRF blocklist.
- `browser_add` and `graphic_art` require human approval when called by agents.
