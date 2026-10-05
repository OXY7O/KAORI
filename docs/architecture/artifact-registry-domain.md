# Artifact Registry Domain

Issue #558 defines the provider-neutral Registry direction. Artifact Registry operational work is split across
#895 (inventory), #896/#915 (security), #897 (runtime correlation), #898 (governance), and #899 (analytics).

## Responsibility Boundary

```text
Integrations → Registry → Harbor → <Instance>
    = provider connection, compatibility, validation, runtime health

Artifact Registry
    = committed inventory, security evidence, governance evidence,
      runtime correlation, analytics, reporting context
```

Harbor remains the provider authority. KAORI normalizes, commits, correlates, governs, and presents evidence.

## Synchronization Topology

Large Registry estates must not run every Artifact Registry concern inside one provider synchronization.

```text
Artifact Registry Inventory Sync
→ Projects / Repositories / Artifacts / Tags
→ stable committed identities
        │
        ├── Artifact Registry Security Sync
        │     → scan / vulnerability / signature / SBOM evidence
        │
        ├── Artifact Registry Governance Sync
        │     → retention / immutability / webhook / replication evidence
        │
        ├── Artifact Registry Runtime Correlation
        │     → committed Registry ↔ current Kubernetes Pod inventory
        │
        └── Artifact Registry Analytics
              → committed materialization
```

The inventory job is the correctness path and must stay bounded. Security, governance, runtime correlation,
and analytics are independently registered Job Executions with their own deduplication, progress, scheduling,
and failure evidence.

Global **Sync All Inventory** dispatches inventory jobs only. It must not implicitly trigger Registry
security, governance, correlation, or analytics work.

## Inventory Contract

The Harbor inventory collector reads provider pages for Projects, Repositories, Artifacts, and Tags only.
It does not fetch per-artifact vulnerability reports, governance policy detail, or Kubernetes runtime data.

Committed identities are reconciled in place using the provider-neutral keys:

```text
Registry Instance
→ Project / Namespace name
→ Repository name
→ Artifact digest
→ Tag name
```

Normal inventory refresh must preserve row identity for unchanged Projects, Repositories, and Artifact
digests so downstream Security, Governance, Runtime Correlation, and Analytics evidence is not destroyed
and rebuilt unnecessarily. Only provider objects that genuinely disappear are deleted.

Once a Registry instance has a committed snapshot, that snapshot remains **ready** while a newer inventory
refresh is collecting and if that refresh later fails. Active execution state belongs to canonical
Job Execution; `RegistryCollectionState.status` describes committed snapshot usability. The failed
attempt is retained in `last_error` without making the prior committed inventory unavailable to Security or
other committed-state consumers.

## Harbor Security Scale Contract

Security refresh is intentionally independent from inventory because Harbor estates may contain hundreds or
thousands of artifacts.

The Harbor security collector first uses paginated repository artifact listings with provider-supported
scan/signature/SBOM summary flags. Full vulnerability report detail is requested only for artifacts whose
scan identity changed or that do not yet have committed scan evidence.

```text
repository artifact page
→ scan/signature/SBOM summary
→ compare with committed security state
    ├── unchanged → reuse committed vulnerability detail
    └── new/changed → fetch vulnerability report detail
```

KAORI never triggers provider scans from this path. A slow or failed security refresh must not invalidate
committed inventory.

Harbor security discovery keeps enriched artifact pages bounded to 20 records and retries one failed
repository discovery with a smaller 10-record page before treating that repository as unavailable for the
current refresh. The configured provider timeout remains authoritative for every request attempt, while the
Harbor client still applies at most two transient transport retries with exponential backoff.

Authentication failures remain source-wide and fail fast. Transport or non-auth provider-response failures
are isolated at repository scope: KAORI retains the repository's previous committed security evidence,
continues other repositories, and completes the canonical Security Sync as partial/warning when at least one
repository refreshed successfully. The provider fails only when no committed repository can be refreshed.

The existing `inventory` Celery queue is used initially to avoid introducing a new worker topology before
runtime evidence proves it is necessary. If incremental security refresh later causes material queue
contention, a dedicated queue/worker may be introduced using the existing Jobs & Executions queue pattern.

## Governance Contract

Registry governance collection is read-only and independent from inventory. It may collect retention,
immutability, webhook, and replication evidence where the provider supports them. Governance collection
uses the same validated Registry read-contract eligibility as inventory and never mutates provider policy.

The default governance schedule is less frequent than inventory because policy state changes materially less
often than artifact inventory.

## Runtime Correlation Contract

Runtime correlation is a database-only materialization. It joins committed Registry artifacts with the
current committed Kubernetes Pod inventory generation.

Digest matches are authoritative when available. Tag-only matches remain explicitly weaker. No live Harbor
or Kubernetes call is allowed in the correlation materialization path.

## Runtime Usage Workspace

Runtime Usage is the operational blast-radius workspace for committed Artifact Registry × Kubernetes
correlation. It is not a Harbor page and it is not a second vulnerability dashboard.

The default view is provider-neutral and cluster-neutral:

```text
All Registry Sources × All Kubernetes Clusters
```

A Registry source or Kubernetes cluster name appears as the active scope only when the operator explicitly
filters to it. The workspace exposes committed runtime bindings, digest matches, tag matches, and
critical/high security exposure. Digest matches remain stronger evidence than mutable tag matches.

Runtime Usage uses the canonical KAORI server-backed registry pattern: default pagination 5, search and
source/cluster/namespace/match/exposure filters, bounded HTMX replacement, standard table actions, and a
committed-evidence View More modal. Security findings may drill into Runtime Usage by immutable
`artifact_id` so the operator can move directly from vulnerability evidence to the affected runtime
blast radius without performing a live Registry or Kubernetes request.

Correlation prerequisites govern **rematerialization eligibility**, not committed-evidence readability.
Once Runtime Correlation has committed a snapshot, Runtime Usage continues to expose that committed evidence
if a later Registry artifact snapshot or current Kubernetes Pod generation becomes unavailable. The workspace
must surface **Refresh Blocked** with the missing prerequisite and recovery action while keeping the previous
bindings readable. Full-page prerequisite blocking is reserved for the pre-materialization state where no
committed Runtime Correlation snapshot exists.

## Operational UI Contract

Normal Artifact Registry pages read committed KAORI state. Provider calls are worker-owned and never occur
in normal page rendering.

Every asynchronous operation uses the canonical Job Execution lifecycle, shared progress contract,
worker-registration preflight, audit trail, and scheduler policy. Provider-specific collectors remain behind
provider-neutral Artifact Registry contracts.
