# Changelog

## 0.2.0 - 2026-07-11

### Added

- Packaged HATE/v1 schemas and isolated wheel smoke validation.
- Draft 2020-12 JSON Schema validation.
- Canonical Post-PoC gap registry and generated status tables.
- Explicit local plugin execution consent and bounded process execution.
- Parallel CI lanes and OSS governance files.

### Changed

- Local subprocess plugins are denied by default and require
  --allow-local-exec plus signed/trusted external evidence.
- Release and regulated profiles always deny local subprocess plugins.
- Previously ignored JSON Schema constraints are now enforced.

### Known limitations

- Plugin signatures are external evidence, not cryptographically verified.
- Local subprocess mode does not provide filesystem or network isolation.
- product_ready remains false and final release authority remains external.
