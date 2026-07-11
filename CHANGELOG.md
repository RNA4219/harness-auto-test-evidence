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

## 0.3.0 - 2026-07-11

### Added

- Machine-readable responsibility registry for every leaf CLI and HATE/v1 record type.
- HATE-bridge/v1 request/result schemas, explicit handoff, and fail-closed materialization.
- Scope and architecture gates for the P0a/P0b/P1a responsibility freeze.
- product-ops-evidence and owner-side consumer contract fixtures.

### Changed

- Post-P1a public handlers dispatch only through the bridge router.
- v0.2 behavior is isolated behind the frozen compat-v0.2 provider.
- Post-P1a schema entries carry canonical owner and removal-window metadata.

### Compatibility

- P0a/P0b/P1a interfaces remain unchanged.
- Post-P1a CLI names, options, output files, required fields, and normal exit codes remain available through v1.
- product_ready remains false and release authority remains external.

### Distribution

- v0.3.0 wheel and source distribution are published as GitHub Release assets.
- PyPI is intentionally not used as a HATE distribution channel.
