# Vault PKI Public Issuer Evidence — HV-03

`pki_public_evidence.py` implements a bounded, *in-memory* observation
contract for a single explicitly provided Vault PKI mount. Based on the
official HashiCorp PKI HTTP API, its only allowed operations are:

- `LIST /v1/<pki-mount>/issuers` (issuer identifiers and safe labels)
- `GET /v1/<pki-mount>/issuer/<UUID>/json` (public issuer cert and chain)

The AppRole identity is authenticated through the existing scoped Vault client.
The collection permits a maximum of 24 issuers, eight chain certificates per
issuer and 32 DNS SANs. It parses X.509 public certificates in memory, then
projects *only* SHA-256 certificate fingerprint, public serial, subject/issuer,
validity, basic CA constraint, self-issued name posture and DNS SAN. The
response's unknown fields, key identifiers, `private_key`, provider tokens and
raw certificates are never committed by this source contract or placed in
Celery payloads. `self_issued` is not proof of valid self-signature.
Trust and revocation remain `not_evaluated`; CRLs and trust stores have their
own future qualified evidence and policy semantics.

**Compatibility:** Multi-issuer discovery is supported in Vault 1.11+.
For older or unsupported mounts, 403/404 and malformed responses fail closed
with a sanitized error; they do not degrade core Vault API readiness and must
not be reported as zero issuers. Listing **issued leaf certificates** via
`LIST /certs` is intentionally excluded because that is a separate authenticated,
incomplete-by-design enumeration capability (e.g., certificates issued with
`no_store=true` are absent). Privileged `GET /issuer/<id>`, key exports,
issuance, revocation, and key management are strictly out of scope.

**Not yet implemented:** approved PKI mount configuration, canonical issuer
and immutable issued-certificate persistence, per-mount collection/freshness
state, JobExecution worker, role/scope-safe PKI or Certificate UI and real-Vault
UAT. This code is source-contract preparation only; do not advertise PKI
Inventory as Available. Use the dedicated test file
`tests/integrations/test_vault_pki_public_evidence.py` in existing QA gates.
See https://developer.hashicorp.com/vault/api-docs/secret/pki for provider
source API behavior.
