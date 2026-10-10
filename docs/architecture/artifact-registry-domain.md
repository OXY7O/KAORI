# Artifact Registry Domain

Issue #558 defines the provider-neutral Registry direction. Artifact Registry operational work is split across
#895 (inventory), #896/#915 (security), #897 (runtime correlation), #898 (governance), #899 (analytics), and #952 (Registry alert-source analytics / fast Analytics delivery).

## Responsibility Boundary

```text
Integrations → Registry → Harbor → <Instance>
    = provider connection, compatibility, validation, runtime health

Artifact Registry
    = committed inventory, security evidence, governance evidence,
      runtime correlation, analytics, reporting context
```

Harbor remains the provider authority. KAORI normalizes, commits, correlates, governs, and presents evidence.

The application dependency direction remains one-way: central Intelligence consumes committed Registry
evidence through the canonical `app.integrations.registry.security_contracts` boundary; Registry
presentation consumes report **definitions** through the existing `app.definitions.loader` rather than
importing the Reports application catalog. Reports remain responsible for rendering their output from
committed Registry state. This avoids circular domain imports without changing the accepted workspace
or inventing a separate catalog, compatibility policy, or report ownership model.

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

Task registration and queue routing remain explicit string-literal entries in the canonical
`app/config/default.py` Celery configuration so the existing Celery topology verifier can audit
all registered task modules, routes, and consumed worker queues. Development and production
worker shell commands use escaped Compose environment expansion (`${...}`) consistent with
existing KAORI workers; Registry Security does not introduce a separate routing registry.

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

Runtime evidence from large Harbor estates established that Security Sync can occupy a worker for tens of
minutes while inventory correctness must remain independently schedulable. Artifact Registry Security
therefore owns the provider-neutral `registry-security` Celery queue and dedicated
`registry-security-worker`.

The fleet Job Execution fans out at **Registry instance** scope only. Each eligible Registry instance becomes
one bounded source task on the dedicated queue; repositories and artifacts remain internal collector work
and are never expanded into one Celery task per artifact. The initial worker concurrency is 2 with prefetch
1, allowing the current two large Registry sources to progress independently while keeping provider pressure
bounded. Additional Registry providers or instances reuse the same queue and can be served by horizontally
scaled workers without introducing provider-specific worker names.

The canonical fleet Job Execution remains the audit, deduplication, heartbeat, and aggregate progress
authority. Concurrent source tasks publish monotonic aggregate progress through row-locked execution
metadata. A slow or failed source cannot consume the inventory worker and does not invalidate committed
inventory or another source's committed security evidence.

## Governance Contract

Registry governance collection is read-only and independent from inventory. It may collect retention,
immutability, webhook, and replication evidence where the provider supports them. Governance collection
uses the same validated Registry read-contract eligibility as inventory and never mutates provider policy.

The default governance schedule is less frequent than inventory because policy state changes materially less
often than artifact inventory.

## Vulnerability Findings Registry: compact list and committed detail (#948)

The Vulnerability Findings workspace keeps the existing Security Evidence
interpretation block (#948) and distinguishes collected findings from scan
coverage; a filtered or zero-result view never proves the Registry estate is
fully scanned. The bounded HTMX Vulnerability Registry retains its canonical
5-row default pagination, filter controls and source/permission scope.

For operator scanability the table uses six aligned columns:
**Finding (19%) / Artifact (21%) / Package & Fix (23%) /
Runtime Exposure (14%) / Evidence (13%) / Details (10%)**.
Finding contains one CVE identifier and one severity badge, not redundant
severity prose and duplicate severity badges. Following human DevContainer
feedback, **Finding, Artifact, and Evidence restore the established KAORI
icon-bearing `table_ui.title_cell` component** (`shield-alert`,
`package-search`, and `blocks`). The icons are navigational reading cues,
not additional severity or scan-state claims. Artifact displays repository and
project without a truncated raw digest. Package shows its name, installed
version and provider-observed fix availability; full fixed-version evidence
moves to the detail. Evidence shows Registry source and freshness; timestamp,
provider and immutable digest remain available in the read-only modal.

Each committed `RegistryVulnerability.id` generates one native **View More**
modal for that page of findings. The modal reuses the existing KAORI Registry
security shell and exposes the full CVE/severity, package and installed/fixed
versions, project/repository/digest, provider/source, scan timestamp,
freshness, and correlation count. A per-artifact **Open Runtime Usage** link
appears only when committed `RegistryWorkloadBinding` evidence exists and
is routed by immutable artifact ID. **Not Observed** has neutral/unknown
presentation, not a success/healthy implication: no committed workload
binding does **not** mean remediated, no vulnerability, or no exposure outside
the materialized correlation scope. Neither the table nor the dialog requests
a live scanner/provider report, triggers provider scans or mutates findings.
Harbor remains provider-authoritative; KAORI normalizes and correlates.

### Vulnerability View More: Supply Chain evidence hierarchy (#948 follow-up)

After DevContainer visual feedback, the native Vulnerability detail modal reuses
the **existing Supply Chain evidence-card hierarchy** rather than presenting one
large generic information card. The shared KAORI security `shell` remains
authoritative for the hero/header, accessible close/focus, scrollable body,
responsive width and evidence footer. Within it, three focused cards present:

1. **Finding & Remediation:** heading icon, canonical severity and runtime
   binding state, full-width affected package, then side-by-side installed and
   fixed version on wider screens, followed by the provider-observed fix note.
2. **Affected Artifact:** project/repository plus a full-width, immutable
   digest band with fingerprint icon.
3. **Runtime & Scan Evidence:** committed binding count, freshness, provider,
   source and observed timestamp, ending with either a link to Runtime Usage
   or an explicit neutral statement about missing committed correlations.

All variable-width values are inside `min-w-0` content slots with
`[overflow-wrap:anywhere]`; opaque versions and digests additionally use
`break-all`. Responsive definition-list grids start as a single column
and only switch to two columns at `sm`, with package, digest and timestamp
available across a complete row. Long package names, unbroken repository
identifiers, versions and digest strings **must never overlap other columns,
modal controls or the footer**. Values are not truncated in the detail view.
The existing canonical scanner evidence, provider authority, runtime
interpretation, conditional Runtime Usage navigation and read-only behavior
are unchanged. No new design-system component or provider request was added.

Visual QA must explicitly test one-character-wide/no-space long strings,
short and long digests, long fixed-version labels, mobile and desktop widths,
modal scroll, light/dark colors, keyboard focus and both runtime-binding
states. CI/CD, Full Admission, UAT and promotion remain HOLD.

Developer Check and local Visual QA should confirm long CVE IDs, package
versions, repository names, digest wrapping, current/stale scan evidence,
Critical/High severity, both runtime binding paths, 5/50-page navigation,
responsive light/dark layouts and keyboard dialog focus. CI/CD,
Full Admission, staging UAT/deployment and promotion remain **HOLD** pending
explicit human acceptance.

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
must keep the committed evidence visible and surface **Refresh Unavailable** only in the Correlation Snapshot
status/description; it must not render a second blocking banner above readable data. Full-page prerequisite
blocking is reserved for the pre-materialization state where no committed Runtime Correlation snapshot exists.

## Registry Alert Analytics Contract

Artifact Registry alert analytics extends the same Alert Source architecture already used by Kubernetes and
Object Storage. It does not introduce a Registry-local Alertmanager client or binding model.

```text
Alertmanager
  → Alert Source / IntegrationBinding
  → registry_instance
  → Analytics worker materialization
  → RegistryAnalyticsSnapshot.alerts
  → Artifact Registry → Analytics → Alerts
```

Alertmanager is the primary alert-state authority. When Alertmanager is not eligible or available, the
bound Metrics Source may provide bounded active-alert fallback evidence through the canonical
`ALERTS{alertstate=~"pending|firing"}` query path. Both sources are read by worker materialization; normal
Registry page rendering never performs live Alertmanager, Prometheus, or Thanos requests.

The canonical consumer profile is `registry-alerts-v1` for `registry_instance`. Shared sources require
selector isolation and existing bindings must be revalidated so the canonical consumer profile and
capability evidence are recorded.

Alert-source failure is an observability dependency only. It does not invalidate committed Registry
inventory, security, runtime, or governance truth.

## Analytics Fast-Shell Contract

Artifact Registry Analytics uses the same bounded delivery principle as the canonical operational dashboard:

```text
GET /artifact-registry/analytics
  → fast shell
  → lazy Analytics Summary
  → lazy active workspace section
```

Inactive Analytics tabs are not rendered before first paint. Growth, Capacity, Usage, Risk, Governance,
Alerts, and Insights remain separate analytical projections over committed materialization.

## Operational UI Contract

Normal Artifact Registry pages read committed KAORI state. Provider calls are worker-owned and never occur
in normal page rendering.

Every asynchronous operation uses the canonical Job Execution lifecycle, shared progress contract,
worker-registration preflight, audit trail, and scheduler policy. Provider-specific collectors remain behind
provider-neutral Artifact Registry contracts.
