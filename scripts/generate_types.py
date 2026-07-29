"""Generate TypeScript type definitions from the FastAPI OpenAPI schema.

Usage:
    python scripts/generate_types.py [--output ../canvas_app/frontend/src/api/types.ts]

Starts the FastAPI app temporarily, fetches the OpenAPI schema, and
generates TypeScript interfaces for all schemas.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vajra_gate import app  # noqa: E402

TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "array": "unknown[]",
    "object": "Record<string, unknown>",
}

SKIP_PREFIXES = ("ValidationError", "HTTPError", "Error")


def _ts_type(schema: dict, schemas: dict[str, dict]) -> str:
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return ref
    if schema.get("type") == "array":
        items = schema.get("items", {})
        return f"{_ts_type(items, schemas)}[]"
    if schema.get("type") == "object":
        if "additionalProperties" in schema:
            val_type = _ts_type(schema["additionalProperties"], schemas)
            return f"Record<string, {val_type}>"
        return "Record<string, unknown>"
    if "enum" in schema:
        return " | ".join(json.dumps(v) for v in schema["enum"])
    if schema.get("oneOf"):
        return " | ".join(_ts_type(s, schemas) for s in schema["oneOf"])
    if schema.get("anyOf"):
        return " | ".join(_ts_type(s, schemas) for s in schema["anyOf"])
    if schema.get("nullable"):
        return f"{TYPE_MAP.get(schema.get('type', ''), 'unknown')} | null"
    return TYPE_MAP.get(schema.get("type", ""), "unknown")


def generate_types() -> str:
    openapi = app.openapi()
    schemas = openapi.get("components", {}).get("schemas", {})
    lines: list[str] = [
        "// Auto-generated from OpenAPI schema. Do not edit manually.",
        f"// Generated at: {__import__('datetime').datetime.now().isoformat()}",
        f"// Schema version: {openapi.get('info', {}).get('version', 'unknown')}",
        "",
    ]

    for name, schema in schemas.items():
        if any(name.startswith(p) for p in SKIP_PREFIXES):
            continue

        required = set(schema.get("required", []))
        properties = schema.get("properties", {})

        if not properties:
            lines.append(f"export type {name} = Record<string, unknown>;")
            lines.append("")
            continue

        lines.append(f"export interface {name} {{")
        for prop_name, prop_schema in properties.items():
            ts_type = _ts_type(prop_schema, schemas)
            optional = prop_name not in required
            opt_mark = "?" if optional else ""
            lines.append(f"  {prop_name}{opt_mark}: {ts_type};")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TypeScript types from OpenAPI schema")
    parser.add_argument("--output",
                        default=os.path.join(
                            os.path.dirname(__file__),
                            "..", "canvas_app", "frontend", "src", "api", "types.ts"
                        ),
                        help="Output path for TypeScript types")
    args = parser.parse_args()

    output = generate_types()
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    type_count = output.count("export interface")
    print(f"Generated {type_count} TypeScript types → {output_path}")


if __name__ == "__main__":
    main()
