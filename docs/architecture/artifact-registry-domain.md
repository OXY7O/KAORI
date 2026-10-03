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


## Security evidence boundary

Issue #896 extends the committed Artifact Registry state with provider-neutral security and supply-chain evidence.

```text
RegistryArtifact(digest)
→ RegistryArtifactSecuritySnapshot
   ├── normalized vulnerability summary
   ├── RegistryVulnerabilityFinding[]
   ├── signature presence metadata
   ├── trust evaluation state
   └── SBOM availability metadata
```

Harbor is the first collector and may expose Trivy-produced vulnerability metadata plus artifact accessories. KAORI does not trigger scans, generate SBOMs, verify signatures, or replace provider-native security engines.

Provider capability state is explicit and may differ by provider:

```text
supported_observed
supported_unavailable
unsupported
not_collected
```

The common Security workspace therefore never assumes that ECR, Google Artifact Registry, ACR, GHCR, Docker Hub, Harbor, or another OCI Registry expose equivalent scanners, signature metadata, or SBOM metadata.

Signature presence and trust are deliberately separate facts. A signature accessory may be observed while `trust_state` remains `not_evaluated`. This prevents KAORI from implying policy verification it did not perform.

Vulnerability findings remain committed evidence. They are not copied one-for-one into Alert Intelligence. Escalation belongs to later cross-domain intelligence where severity, fixability, runtime deployment, policy sensitivity, and other operational context can be correlated.


## Kubernetes runtime correlation

Issue #897 materializes cross-domain bindings from committed Artifact Registry and Kubernetes inventory. No correlation page performs a live Registry or Kubernetes API request.

```text
committed RegistryArtifact(digest)
        +
committed PodInventory container image/imageID evidence
        ↓
RegistryWorkloadBinding
        ↓
Runtime Usage / blast radius
```

Matching precedence is conservative:

1. A digest from Kubernetes `imageID` or the image reference is preferred.
2. When a repository path is present, it must agree with the canonical Registry project/repository path.
3. When an explicit registry host is present, it must agree with provider-normalized `registry_hosts` evidence.
4. A unique digest match is `authoritative`.
5. Only when no digest exists may a unique repository + tag match be recorded as `weak`.
6. Multiple candidates are recorded as ambiguous with no canonical artifact binding.
7. Unmatched references remain visible as evidence; KAORI does not invent a Registry identity.

Harbor publishes normalized registry host aliases during its normal inventory collection. Future Registry adapters should publish equivalent host aliases without changing correlation logic.

Each materialized row preserves both evidence sides: Registry provider/source and Registry observation time, Kubernetes cluster/namespace/Pod/container and Kubernetes observation time, plus the original image reference and runtime image ID.

The Runtime Usage view is protected by `artifact_registry.runtime_correlation.view`, which depends on both `artifact_registry.view` and `inventory.view`. Vulnerability rows can drill into an artifact-scoped runtime blast radius without weakening this cross-domain authorization boundary.
