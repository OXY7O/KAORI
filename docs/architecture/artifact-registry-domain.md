# Artifact Registry Domain

## Authority

Issue #558 defines the Registry/Harbor architecture direction. Issue #895 establishes the first operational Artifact Registry slice.

The product boundary is intentionally split:

```text
Integrations → Registry → Provider → Instance
    = provider registration, credentials, compatibility, validation, runtime health

Artifact Registry
    = committed inventory, security posture, governance, correlation, analytics
```

Harbor is the first provider. It is not the Artifact Registry domain identity.

## Canonical identity

Artifact identity is digest-oriented:

```text
IntegrationInstance(type=registry)
→ RegistryProject
→ RegistryRepository
→ RegistryArtifact(digest)
→ RegistryTag
```

A tag is a mutable alias. When a digest exists, KAORI never uses a tag as the immutable artifact identity.

Provider-native identifiers and metadata are retained as evidence, but canonical tables and UI concepts remain provider-neutral.

## Collection authority

Normal operational pages read committed KAORI state.

```text
Registry provider API
→ provider collector
→ normalized evidence contract
→ per-source reconciliation transaction
→ PostgreSQL committed snapshot
→ Artifact Registry UI
```

The initial Harbor collector reads Harbor API v2.0 Projects, Repositories, Artifacts, and Tags. It performs no provider mutation.

Inventory synchronization is a registered canonical Job Execution on the `inventory` queue. Each Registry source is committed independently after successful collection. If discovery unexpectedly returns zero projects while a previous committed snapshot exists, KAORI preserves the prior snapshot instead of interpreting the empty response as authoritative deletion.

## Multi-provider contract

Future providers such as AWS ECR, Google Artifact Registry, Azure Container Registry, GitHub Container Registry, Docker Hub, and OCI Distribution implementations must plug into the same normalized collector boundary.

Provider differences are expressed as capability/evidence availability, not by forking the Artifact Registry domain model or navigation.

A provider-specific feature may be:

- supported and observed;
- supported but currently unavailable;
- unsupported by that provider;
- not yet collected.

No common UI should fabricate evidence to make providers appear symmetrical.

## Workspace

```text
Artifact Registry
├── Overview
├── Inventory
│   ├── Projects
│   ├── Repositories
│   └── Artifacts
├── Security       # issue #896
├── Governance     # issue #898
└── Analytics      # issue #899
```

Kubernetes runtime correlation is owned by issue #897 and joins committed Registry artifact evidence with committed Kubernetes inventory.

The provider prerequisite blocker routes setup back to `Integrations → Registry`. Provider registration remains separate from operational inventory.

## RBAC

- `artifact_registry.view`: view committed Artifact Registry evidence.
- `artifact_registry.sync`: run inventory synchronization; depends on `artifact_registry.view` and `jobs.execute`.

Viewer and Auditor receive read access. Operator, Editor, and Admin receive read plus sync access.

## Non-goals

The foundation does not:

- clone Harbor;
- delete artifacts, repositories, or projects;
- mutate retention, immutability, or replication;
- trigger provider garbage collection;
- trigger scans;
- render operational pages from live provider requests;
- publish each vulnerability directly into Alert Intelligence.

Those boundaries remain explicit for later workstreams.
