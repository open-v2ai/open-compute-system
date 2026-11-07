"""Export FastAPI OpenAPI and generate dependency-free TypeScript schema types."""

import json
import sys
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402, I001


ROOT = API_ROOT.parent
OUTPUT = ROOT / "web" / "lib" / "api" / "generated"


def ts_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        values = [ts_type(item) for item in schema["anyOf"]]
        return " | ".join(dict.fromkeys(values))
    if "enum" in schema:
        return " | ".join(json.dumps(item, ensure_ascii=False) for item in schema["enum"])
    schema_type = schema.get("type")
    if schema_type == "array":
        return f"Array<{ts_type(schema.get('items', {}))}>"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"Record<string, {ts_type(additional)}>"
        return "Record<string, unknown>"
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
    }.get(schema_type, "unknown")


def generate_types(openapi: dict[str, Any]) -> str:
    lines = [
        "// Generated from FastAPI OpenAPI. Do not edit by hand.",
        "",
    ]
    for name, schema in openapi.get("components", {}).get("schemas", {}).items():
        properties = schema.get("properties")
        if not properties:
            lines.append(f"export type {name} = {ts_type(schema)};\n")
            continue
        required = set(schema.get("required", []))
        lines.append(f"export interface {name} {{")
        for field, field_schema in properties.items():
            optional = "" if field in required else "?"
            lines.append(f"  {json.dumps(field)}{optional}: {ts_type(field_schema)};")
        lines.append("}\n")
    return "\n".join(lines)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    openapi = app.openapi()
    (OUTPUT / "openapi.json").write_text(
        json.dumps(openapi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "schema.ts").write_text(generate_types(openapi), encoding="utf-8")
    print(f"Generated OpenAPI artifacts in {OUTPUT}")


if __name__ == "__main__":
    main()
