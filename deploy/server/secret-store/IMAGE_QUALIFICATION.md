# OpenBao 2.7.3 image candidate — source and registry evidence (#5202)

Observed 2026-11-25 WIB. This is a source/registry review, not runtime,
provenance, vulnerability or deployment admission. Keep the existing
operator-bootstrap profile inactive until the remaining checks pass.

## Exact upstream candidate

- [Release notes](https://openbao.org/community/release-notes/2-7-0/): v2.7.3, 2026-11-19.
- Distribution: official Alpine image `docker.io/openbao/openbao`.
- Registry index: `sha256:ba4b133eb9586630024e71a617e66f37f29cc3534cdd46a6233e098ceded8dc9`.
- [linux/amd64 manifest](https://hub.docker.com/layers/openbao/openbao/2.7.3/images/sha256-b9418c63e2185157d8ee8689a8a93265d5aadad677d6320156172bd42ad3b10b): `sha256:b9418c63e2185157d8ee8689a8a93265d5aadad677d6320156172bd42ad3b10b`.
- [linux/arm64 manifest](https://hub.docker.com/layers/openbao/openbao/2.7.3/images/sha256-6a68ede0364092d8b93c12f8ea3b8ff1305925a8024511354a0d79a7cca68f23): `sha256:6a68ede0364092d8b93c12f8ea3b8ff1305925a8024511354a0d79a7cca68f23`.
- Source [LICENSE](https://github.com/openbao/openbao/blob/v2.7.3/LICENSE) is MPL-2.0; the [Dockerfile](https://github.com/openbao/openbao/blob/v2.7.3/Dockerfile) includes it in the image. Retain actual image/license and dependency SBOM evidence before admission.

Proposed target-owned `KAORI_SECRET_STORE_IMAGE` after admission:

```text
docker.io/openbao/openbao@sha256:ba4b133eb9586630024e71a617e66f37f29cc3534cdd46a6233e098ceded8dc9
```

The registry listing is not signature verification. Verify the index and selected
platform manifest on the authorized runner, upstream provenance/signature or
documented equivalent evidence, license, current vulnerability scan, and
`bao version` before loading the overlay. The actual host architecture and
image identity must match the evidence. Do not use mutable tags.

## Entrypoint and private mounts

The exact [v2.7.3 entrypoint](https://github.com/openbao/openbao/blob/v2.7.3/.release/docker/docker-entrypoint.sh)
adds the config directory to the server invocation itself and can attempt to
change directory ownership. The Alpine image declares the non-root
`openbao` user. The candidate overrides the upstream dev command with
`server` only, sets `SKIP_CHOWN=1`, drops all capabilities, and keeps the
configuration mount read-only. No duplicate explicit config flag, no
`BAO_LOCAL_CONFIG`, no dev root token, no root override. The private service
env must contain only its approved storage DSN. Mount only the reviewed HCL
and required TLS files; the host owner must provision correct file access
for the actual image UID/GID and writable audit directory before startup.
Do not loosen permissions or run the server as root to resolve a failure.

## Remaining qualification

- Read-only exact image pull/inspect, UID/GID, version and signature/provenance
  checks, SBOM, license and Trivy results on an authorized disposable runner.
- Validate composed mounts, command, network, no public ports, capability
  drops and memory/swap behavior with the actual engine. The resource limit
  remains a benchmark candidate.
- Verified PostgreSQL TLS and dedicated DB, correct HCL and audit device;
  genuine uninitialized/sealed/active lifecycle under operator custody,
  independent recovery, restart and actual provider compatibility.

No image was pulled or executed by this source review. No RC, live deployment
or reset is authorized by this record.
