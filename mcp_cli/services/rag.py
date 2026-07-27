from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_cli.services.chunker import chunk_by_tokens, extract_text
from mcp_cli.services.logging import get_logger

if TYPE_CHECKING:
    from mcp_cli.services.claude import Claude
    from mcp_cli.services.vector_store import VectorStore

logger = get_logger(__name__)

_DEFAULT_NAMESPACE = "documents"


class RagPipeline:
    def __init__(self, claude: Claude, vector_store: VectorStore):
        self.claude = claude
        self.vector_store = vector_store

    async def index_document(
        self,
        content: bytes,
        filename: str,
        namespace: str = _DEFAULT_NAMESPACE,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> dict[str, Any]:
        text = extract_text(content, filename)
        if not text.strip():
            logger.warning("No extractable text in %s", filename)
            return {"filename": filename, "chunks": 0, "error": "no extractable text"}

        chunks = chunk_by_tokens(text, chunk_size=chunk_size, overlap=chunk_overlap)
        indexed = 0
        errors: list[str] = []

        for i, chunk in enumerate(chunks):
            key = f"{filename}#chunk_{i}"
            emb = await self.claude.embed(chunk["text"])
            if not emb:
                errors.append(key)
                continue
            await self.vector_store.async_index(
                namespace=namespace,
                key=key,
                text=chunk["text"],
                embedding=emb,
                metadata={"filename": filename, "chunk_index": i, "source": filename},
            )
            indexed += 1

        result: dict[str, Any] = {
            "filename": filename,
            "total_chunks": len(chunks),
            "indexed": indexed,
        }
        if errors:
            result["errors"] = errors
            result["error"] = f"{len(errors)} chunks failed to embed"
        if indexed > 0:
            logger.info("Indexed %d/%d chunks from %s", indexed, len(chunks), filename)
        return result

    async def retrieve(
        self,
        query: str,
        namespace: str = _DEFAULT_NAMESPACE,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        emb = await self.claude.embed(query)
        if not emb:
            return []
        results = await self.vector_store.async_search(emb, namespace=namespace, limit=top_k)
        if min_score > 0:
            results = [r for r in results if r["score"] >= min_score]
        return results

    def format_context(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return ""
        parts: list[str] = []
        for i, r in enumerate(results):
            source = r.get("metadata", {}).get("filename", "unknown")
            parts.append(
                f"[{i + 1}] (source: {source}, score: {r['score']:.3f})\n{r['text']}"
            )
        return "\n\n---\n\n".join(parts)

    async def list_documents(self, namespace: str = _DEFAULT_NAMESPACE) -> list[dict[str, Any]]:
        keys = await self.vector_store.async_list_keys(namespace)
        if not keys:
            return []
        filenames: dict[str, int] = {}
        for k in keys:
            name = k.split("#chunk_")[0]
            filenames[name] = filenames.get(name, 0) + 1
        return [
            {"filename": name, "chunks": count}
            for name, count in sorted(filenames.items())
        ]

    async def delete_document(self, filename: str, namespace: str = _DEFAULT_NAMESPACE) -> int:
        keys = await self.vector_store.async_list_keys(namespace)
        matching = [k for k in keys if k.startswith(f"{filename}#")]
        deleted = 0
        for key in matching:
            await self.vector_store.async_delete(namespace, key)
            deleted += 1
        return deleted
