from __future__ import annotations

from pathlib import Path

from hate.schema_resources import read_schema, validate_all_schema_documents, validate_schema_instance


def _messages(value: object, schema: dict) -> list[str]:
    return [error.message for error in validate_schema_instance(value, schema)]


def test_draft_2020_constraints_are_enforced() -> None:
    assert _messages(2, {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "number", "maximum": 1})
    assert _messages([], {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "array", "minItems": 1})
    assert _messages(["x", "x"], {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "array", "uniqueItems": True})
    assert _messages("not-a-date", {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "string", "format": "date-time"})
    assert _messages({}, {"$schema": "https://json-schema.org/draft/2020-12/schema", "anyOf": [{"required": ["actor"]}, {"required": ["system_actor"]}]})
    assert _messages(1, {"$schema": "https://json-schema.org/draft/2020-12/schema", "oneOf": [{"type": "number"}, {"type": "integer"}]})


def test_missing_external_ref_is_reported() -> None:
    errors = validate_schema_instance(
        {},
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://hate.local/schemas/HATE/v1/missing-ref-test.schema.json",
            "$ref": "does-not-exist.schema.json",
        },
    )

    assert errors
    assert "unresolved schema reference" in errors[0].message


def test_all_published_schemas_are_valid_draft_2020_documents() -> None:
    assert validate_all_schema_documents() == []


def test_explicit_schema_root_remains_supported(tmp_path: Path) -> None:
    source = read_schema("run.schema.json")
    (tmp_path / "run.schema.json").write_text(
        __import__("json").dumps(source),
        encoding="utf-8",
    )

    assert read_schema("run.schema.json", schema_root=tmp_path)["title"] == source["title"]
