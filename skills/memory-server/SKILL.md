# Memory Server

Persistent knowledge graph memory via `@modelcontextprotocol/server-memory`. Stores entities, relations, and observations.

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `add_entities` | `(entities: list[dict]) -> str` | Add entities with optional observations |
| `add_relations` | `(relations: list[dict]) -> str` | Add relations between entities (source, target, relation type) |
| `add_observations` | `(observations: list[dict]) -> str` | Add observations to existing entities |
| `delete_entities` | `(entity_names: list[str]) -> str` | Delete entities by name |
| `delete_observations` | `(deletions: list[dict]) -> str` | Delete specific observations from entities |
| `delete_relations` | `(relations: list[dict]) -> str` | Delete relations between entities |
| `read_graph` | `() -> dict` | Read the entire knowledge graph |
| `search_nodes` | `(query: str) -> dict` | Search nodes by query string |
| `open_nodes` | `(names: list[str]) -> dict` | Get full details of specific entities |

## Entity Schema

```json
{
  "name": "str",
  "entityType": "str (optional)",
  "observations": ["str", ...]
}
```

## Relation Schema

```json
{
  "source": "str",
  "target": "str",
  "relationType": "str"
}
```
