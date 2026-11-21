# KAORI

**Knowledge, Automation, Operations, Resilience & Intelligence**

**Evidence-driven infrastructure operations for Kubernetes and connected platforms.**

KAORI transforms committed infrastructure evidence into actionable inventory, observability, analytics, governance, and controlled operational workflows. It complements the systems that execute work and provide telemetry; it does not replace their authority.

> **An operational evidence platform, not another monitoring engine.** Providers remain authoritative. KAORI normalizes and correlates their evidence, supports governed decisions, and preserves auditability.

## What KAORI provides

| Capability | Operational value |
| --- | --- |
| **Infrastructure inventory** | Committed snapshots and contextual visibility across Kubernetes and supported integrations. |
| **Observability integrations** | Operational context from Prometheus/Thanos metrics and Alertmanager signals. |
| **Storage operations** | S3-compatible object-storage evidence and integration workflows. |
| **Analytics & intelligence** | Reports, recommendations, and cross-domain operational interpretation. |
| **Governance & automation** | Auditable approvals, controlled workflows, and explicit remediation boundaries. |

Capabilities depend on the supported release and configured integrations; a published image tag alone does not indicate that every optional provider or feature is enabled.

## Get started

This repository distributes the **KAORI application runtime image**. It is **not** a standalone single-container appliance: supported operation also requires the application database, Redis, migrations, and web/background services in an appropriate deployment topology.

| Use case | Supported path |
| --- | --- |
| **Evaluate an admitted release candidate locally** | [Standalone Docker Compose example](https://github.com/OXY7O/KAORI/tree/main/example/kaori) |
| **Deploy to a governed server** | [Deployment guide](https://github.com/OXY7O/KAORI/blob/main/docs/DEPLOYMENT.md) and [server adapter](https://github.com/OXY7O/KAORI/tree/main/deploy/server) |
| **Develop or contribute to source** | [Development environment](https://github.com/OXY7O/KAORI/blob/main/docs/DEVELOPMENT.md) |

Before deployment, select an **admitted image identity** from the release evidence. A digest-qualified pull looks like:

```bash
# Replace <approved-digest> with the exact digest from accepted release evidence.
docker pull lethisaputri/kaori@sha256:<approved-digest>
```

Use the matching deployment example or governed server procedure to configure PostgreSQL, Redis, workers, secrets, and release metadata. Do not deploy by running the image in isolation.

## Image versions and provenance

| Image reference | Meaning |
| --- | --- |
| `vX.Y.Z-rc.N` | Release candidate; evaluate only under the applicable admission/UAT contract. |
| `vX.Y.Z` | Stable release, published only after governed acceptance and promotion. |
| `@sha256:<digest>` | Immutable image identity used by governed deployment and rollback evidence. |
| `latest` | **Not published as a release contract.** Do not depend on it. |

KAORI uses Semantic Versioning, exact source revisions, and immutable OCI image digests. Stable promotion reuses the accepted image digest **without rebuilding application bits**. A repository README or a tag label is not proof that an image has been admitted for a particular environment.

For version authority, release evidence, and rollback policy, see [Release Lifecycle](https://github.com/OXY7O/KAORI/blob/main/docs/releases/README.md) and [Release Governance](https://github.com/OXY7O/KAORI/blob/main/docs/deployment/RELEASE_GOVERNANCE.md).

## Security and responsible use

KAORI's governed release process includes security and supply-chain validation gates. Check the **evidence associated with the specific image digest** before relying on a scan, SBOM, provenance attestation, signature, or deployment status; do not infer validation from the presence of a tag.

Keep credentials, database passwords, private endpoints, and production configuration outside images and public example files. Report vulnerabilities privately under the [Security Policy](https://github.com/OXY7O/KAORI/blob/main/SECURITY.md).

## Licensing and project

KAORI-authored software source is licensed under [Apache-2.0](https://github.com/OXY7O/KAORI/blob/main/LICENSE), subject to the repository [NOTICE](https://github.com/OXY7O/KAORI/blob/main/NOTICE). Third-party assets retain their respective licenses. The KAORI/OXY7O names, logos, and brand artwork are not granted as trademarks by the software license.

- **Source & documentation:** [OXY7O/KAORI](https://github.com/OXY7O/KAORI)
- **Release history:** [GitHub Releases](https://github.com/OXY7O/KAORI/releases)
- **Container images:** [Docker Hub — lethisaputri/kaori](https://hub.docker.com/r/lethisaputri/kaori)
- **Security:** [Private vulnerability reporting guidance](https://github.com/OXY7O/KAORI/blob/main/SECURITY.md)

---

**KAORI — Committed evidence. Correlated context. Governed action.**
