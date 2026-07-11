from __future__ import annotations

import json

from hate.schema_resources import validate_all_schema_documents


def main() -> int:
    errors = validate_all_schema_documents()
    report = {
        "record_type": "schema-meta-validation",
        "schema_version": "HATE/ci-schema-meta/v1",
        "overall_status": "hold" if errors else "pass",
        "errors": errors,
        "summary": {"error_count": len(errors)},
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
