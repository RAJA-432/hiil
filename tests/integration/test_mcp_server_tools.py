import pytest

from mcp_server.storage.store import get_document
from mcp_server.tools.documents import edit_document, format_document, read_document


@pytest.mark.asyncio
async def test_read_document():
    content = await read_document("report.pdf")
    assert "condenser tower" in content


@pytest.mark.asyncio
async def test_read_document_not_found():
    with pytest.raises(ValueError):
        await read_document("nonexistent.pdf")


@pytest.mark.asyncio
async def test_edit_document_tool():
    original = get_document("spec.txt")
    result = await edit_document("spec.txt", "technical", "functional")
    assert "functional" in result
    await edit_document("spec.txt", "functional", "technical")
    assert get_document("spec.txt") == original


@pytest.mark.asyncio
async def test_format_document_removes_trailing_spaces():
    result = await format_document("hello   \nworld  \n")
    assert result == "hello\nworld\n"


@pytest.mark.asyncio
async def test_format_document_collapses_blank_lines():
    result = await format_document("a\n\n\n\nb")
    assert result == "a\n\nb\n"


@pytest.mark.asyncio
async def test_format_document_ensures_final_newline():
    result = await format_document("no newline at end")
    assert result == "no newline at end\n"


@pytest.mark.asyncio
async def test_format_document_empty():
    result = await format_document("")
    assert result == "\n"


@pytest.mark.asyncio
async def test_format_document_noop():
    text = "clean text\nwith no issues\n"
    result = await format_document(text)
    assert result == text
