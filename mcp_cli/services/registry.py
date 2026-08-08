from dataclasses import dataclass


@dataclass
class ToolCategory:
    name: str
    tools: list[str]
    priority: str  # "CORE" or "EXPERT"

class ToolRegistry:
    def __init__(self):
        # Define the expert pools
        self.categories = {
            "core": ToolCategory("core", ["help", "memory"], "CORE"),
            "web": ToolCategory("web", ["web_search", "web_fetch"], "EXPERT"),
            "fs": ToolCategory("fs", ["read_file", "write_file", "glob"], "EXPERT"),
            "kg": ToolCategory("kg", ["kg_query", "kg_insert"], "EXPERT"),
            "sys": ToolCategory("sys", ["list_tools", "get_status"], "EXPERT"),
            "media": ToolCategory(
                "media",
                ["graphic_art", "search_template_images", "search_template_videos"],
                "EXPERT",
            ),
            "travel": ToolCategory("travel", ["search_airports", "search_flights"], "EXPERT"),
            "health": ToolCategory("health", ["search_healthcare"], "EXPERT"),
            "history": ToolCategory("history", ["browser_search", "browser_add"], "EXPERT"),
        }

        # Keyword mapping for quick routing
        self.keyword_map = {
            "search": "web", "web": "web", "fetch": "web", "url": "web", "site": "web",
            "file": "fs", "read": "fs", "write": "fs", "glob": "fs", "folder": "fs", "dir": "fs", "path": "fs",
            "graph": "kg", "knowledge": "kg", "kg": "kg", "entity": "kg", "relation": "kg",
            "tool": "sys", "status": "sys", "config": "sys",
            "flight": "travel", "flights": "travel", "airport": "travel", "airline": "travel",
            "travel": "travel", "ticket": "travel", "route": "travel", "destination": "travel",
            "health": "health", "healthcare": "health", "symptom": "health", "medical": "health",
            "medicine": "health", "disease": "health", "diagnosis": "health",
            "history": "history", "browser": "history", "visited": "history", "browsing": "history",
            "image": "media", "images": "media", "picture": "media", "photo": "media",
            "video": "media", "videos": "media", "template": "media", "graphic": "media",
            "art": "media", "logo": "media", "banner": "media", "illustration": "media",
        }

    def resolve_tools(self, query: str) -> set[str]:
        """
        Determines which tool schemas should be sent to the LLM based on the query.
        """
        # 1. Always include CORE tools
        selected = set()
        for cat in self.categories.values():
            if cat.priority == "CORE":
                selected.update(cat.tools)

        # 2. Route to Expert Pools based on keywords
        query_lower = query.lower()
        for kw, cat_name in self.keyword_map.items():
            if kw in query_lower:
                selected.update(self.categories[cat_name].tools)

        return selected
