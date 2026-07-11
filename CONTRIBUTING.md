# Contributing to HATE

Thank you for improving HATE. HATE is an advisory evidence normalizer and does
not own final release approval.

## Development workflow

1. Create a focused branch and keep generated runtime output under tmp/.
2. Run relevant targeted tests while developing.
3. Before opening a pull request, run every release check documented in README.
4. Regenerate Birdseye after changing source, tests, schemas, fixtures, or important documentation.
5. Include failure-mode tests and do not broaden product-readiness claims.

## Security-sensitive changes

Plugin execution, artifact handling, schema validation, redaction, tenant
isolation, and release handoff changes require negative tests. Never execute a
local plugin without explicit operator consent.
