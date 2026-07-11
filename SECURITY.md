# Security Policy

## Supported versions

The v0.2.x development line receives security fixes. v0.1.0 is a preview and
must not be used as a security or release authority.

## Reporting a vulnerability

Use GitHub private vulnerability reporting or a repository Security Advisory.
Do not open a public issue for suspected secret exposure, arbitrary command
execution, path traversal, tenant isolation, or redaction bypasses.

## Plugin execution boundary

Local subprocess plugins can execute arbitrary code. HATE requires the
allow-local-exec CLI option and trusted external evidence before starting one.
The signature_valid field is external evidence; HATE v0.2.0 does not perform
cryptographic signature verification. Filesystem and network isolation are not
provided for local subprocess mode. Release and regulated profiles deny that
mode even when consent is supplied.

HATE produces advisory evidence only. It does not grant waivers or final
release approval.
