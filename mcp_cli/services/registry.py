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
        }

        # Keyword mapping for quick routing
        self.keyword_map = {
            "search": "web", "web": "web", "fetch": "web", "url": "web", "site": "web",
            "file": "fs", "read": "fs", "write": "fs", "glob": "fs", "folder": "fs", "dir": "fs", "path": "fs",
            "graph": "kg", "knowledge": "kg", "kg": "kg", "entity": "kg", "relation": "kg",
            "tool": "sys", "status": "sys", "config": "sys",
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
