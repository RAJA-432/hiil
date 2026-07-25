from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_cli.services.document_injector import DocumentInjector


@pytest.mark.asyncio
async def test_initialize_with_client():
    doc_client = AsyncMock()
    doc_client.read_resource = AsyncMock(return_value='["doc1","doc2"]')
    di = DocumentInjector(doc_client)
    await di.initialize()
    assert di.doc_ids == ["doc1", "doc2"]


@pytest.mark.asyncio
async def test_initialize_without_client():
    di = DocumentInjector(None)
    await di.initialize()
    assert di.doc_ids == []


@pytest.mark.asyncio
async def test_initialize_failure():
    doc_client = AsyncMock()
    doc_client.read_resource = AsyncMock(side_effect=Exception("timeout"))
    di = DocumentInjector(doc_client)
    await di.initialize()
    assert di.doc_ids == []


@pytest.mark.asyncio
async def test_resolve_without_client():
    di = DocumentInjector(None)
    result = await di.resolve("see @doc1")
    assert result == "see @doc1"


@pytest.mark.asyncio
async def test_resolve_no_matches():
    doc_client = AsyncMock()
    di = DocumentInjector(doc_client)
    di.doc_ids = ["doc1"]
    result = await di.resolve("hello world")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_resolve_single_doc():
    doc_client = AsyncMock()
    doc_client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="content of doc1")]))
    di = DocumentInjector(doc_client)
    di.doc_ids = ["doc1"]
    result = await di.resolve("see @doc1")
    assert "Document context" in result
    assert "doc1" in result
    assert "content of doc1" in result


@pytest.mark.asyncio
async def test_resolve_all_docs():
    doc_client = AsyncMock()
    doc_client.read_resource = AsyncMock(return_value='["doc1","doc2"]')
    doc_client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="content")]))
    di = DocumentInjector(doc_client)
    di.doc_ids = ["doc1", "doc2"]
    result = await di.resolve("inject @all")
    assert "Document context" in result
    content = result.split("Document context:\n")[1] if "Document context:\n" in result else ""
    assert content.count("<document id=") >= 2


@pytest.mark.asyncio
async def test_resolve_failure_returns_original():
    doc_client = AsyncMock()
    doc_client.call_tool = AsyncMock(side_effect=Exception("fail"))
    di = DocumentInjector(doc_client)
    di.doc_ids = ["doc1"]
    result = await di.resolve("see @doc1")
    assert result == "see @doc1"


@pytest.mark.asyncio
async def test_resolve_with_extract_text():
    class FakeText:
        def __init__(self, t):
            self.text = t

    class FakeContent:
        def __init__(self):
            self.content = [FakeText("extracted content")]

    doc_client = AsyncMock()
    doc_client.call_tool = AsyncMock(return_value=FakeContent())
    di = DocumentInjector(doc_client)
    di.doc_ids = ["doc1"]
    result = await di.resolve("@doc1")
    assert "extracted content" in result
