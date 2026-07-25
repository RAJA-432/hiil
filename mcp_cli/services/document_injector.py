from __future__ import annotations

import json
import re
from typing import Any

from mcp_cli.services.logging import get_logger
from mcp_cli.services.tool_runner import _extract_text as extract_text

logger = get_logger("document_injector")


class DocumentInjector:
    def __init__(self, doc_client: Any | None):
        self.doc_client = doc_client
        self.doc_ids: list[str] = []

    async def initialize(self) -> None:
        if not self.doc_client:
            self.doc_ids = []
            return
        try:
            doc_ids = await self.doc_client.read_resource("docs://documents")
            if isinstance(doc_ids, str):
                doc_ids = json.loads(doc_ids)
            self.doc_ids = list(doc_ids) if doc_ids else []
        except Exception as exc:
            logger.warning("could not list documents for completion: %s", exc)
            self.doc_ids = []

    async def resolve(self, text: str) -> str:
        if not self.doc_client:
            return text
        matches = re.findall(r"(?:^|\s)@(\S+)", text)
        if not matches:
            return text
        all_tokens = {"all", "*"}
        context: list[str] = []
        failed_docs: list[str] = []
        if all_tokens & set(matches):
            try:
                doc_ids = await self.doc_client.read_resource("docs://documents")
                if isinstance(doc_ids, str):
                    doc_ids = json.loads(doc_ids)
            except Exception as exc:
                doc_ids = []
                failed_docs.append(f"docs://documents ({exc})")
            for doc_id in doc_ids or []:
                try:
                    result = await self.doc_client.call_tool("read_document", {"doc_id": doc_id})
                    content = extract_text(result)
                    context.append(f"<document id=\"{doc_id}\">\n{content}\n</document>")
                except Exception as exc:
                    failed_docs.append(f"{doc_id} ({exc})")
            if context:
                logger.info("injected %d documents: %s", len(context), ", ".join(doc_ids))
        else:
            for doc_id in matches:
                try:
                    result = await self.doc_client.call_tool("read_document", {"doc_id": doc_id})
                    content = extract_text(result)
                    context.append(f"<document id=\"{doc_id}\">\n{content}\n</document>")
                except Exception as exc:
                    failed_docs.append(f"{doc_id} ({exc})")
        if failed_docs:
            logger.warning("Failed to load documents: %s", ", ".join(failed_docs))
        if not context:
            return text
        return text + "\n\nDocument context:\n" + "\n\n".join(context)
