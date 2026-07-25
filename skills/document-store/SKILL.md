# Document Store

In-memory document storage with read/edit operations.

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `read_document` | `(doc_id: str) -> str` | Read the full text of a document by its ID. Raises `ValueError` if not found. |
| `edit_document` | `(doc_id: str, old_str: str, new_str: str) -> str` | Replace the first occurrence of `old_str` with `new_str` in the document. Returns updated content. |

## Resources

| URI Pattern | Description |
|-------------|-------------|
| `docs://documents` | List all document IDs (JSON array) |
| `docs://documents/{doc_id}` | Raw document text |

## Available Documents

| ID | Content Summary |
|----|----------------|
| `deposition.md` | Testimony of Angela Smith, P.E. |
| `report.pdf` | State of a 20m condenser tower |
| `financials.docx` | Project budget and expenditures |
| `outlook.pdf` | Projected future performance |
| `plan.md` | Project implementation steps |
| `spec.txt` | Technical requirements for equipment |
