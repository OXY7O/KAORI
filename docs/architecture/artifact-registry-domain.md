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

### Governance Evidence Operations: Security Sync UX parity (#950)

The Governance workspace follows the **same canonical sync interaction** as
Artifact Registry Security, while retaining a separate authoritative job:
`artifact_registry.governance.sync`. The existing Governance JobExecution
collector, read-only provider policy/replication evidence, progress adapter,
polling endpoint and schedule policy remain unchanged. **Governance Sync does
not trigger Security Sync, Inventory Sync, provider-side scans or provider
policy mutations.**

- `governance.html` provides the full-page layout and includes the
  refreshable `partials/_governance_workspace.html`; HTMX GET returns that
  partial so active Policies/Replication workspace views remain independently
  navigable using canonical server-owned content tabs and five-row pagination.
- The sync form submits its CSRF-authenticated request to the **existing**
  `artifact_registry.governance_sync` endpoint through HTMX, targets the
  Governance workspace, prevents a second submit while the canonical
  JobExecution is active, and preserves the selected tab/page/page size.
- HTMX manual sync dispatch renders current committed Governance context and
  an out-of-band operational toast. Standard non-HTMX POST/redirect remains
  available. Active JobExecution progress still polls the existing
  `governance_sync_status` endpoint; on terminal completion it emits
  `artifactRegistryGovernanceSyncFinished` to refresh the workspace using
  committed evidence and notify the existing notification system.
- The **Governance Evidence Operations** panel now groups just the canonical
  sync state, two actions (Sync Governance / Configure Sync) and three
  scheduling facts: Automatic Sync, Last Successful and Next Scheduled.
  The four separate policy/retention/immutability/replication coverage cards
  remain unchanged in meaning but move to their own responsive grid, as in
  Security's separately owned findings/coverage summary.

This is an existing KAORI HTMX/JobExecution pattern, not a new job, registry
provider, UI component, governance calculation or policy interpretation.
DevContainer human Visual QA must cover active/error/completed sync, toast,
no duplicate manual dispatch, tab/page preservation, partial-only HTMX
responses, light/dark mode and mobile widths. Full Admission, CI/CD,
staging/UAT deployment and main promotion remain **HOLD** until explicit
authorization.

### Registry UI Consistency Audit — active workspace family (#1087)

**Scope:** Artifact Registry Overview, Inventory, Security, Runtime Usage,
Governance, and Analytics as present on the current
`kaori/review/staging-uat` implementation. This audit applies the already
approved KAORI Design System v2, `section_intro`, the shared
`operational_metric_card`, `section_card`, tab, table and pagination
components. It does **not** introduce a new page archetype or prescribe the
same nested-card geometry for every domain.

| Workspace | Hero / evidence authority | Summary / section-intro treatment | Navigation / table pattern | Audit decision |
| --- | --- | --- | --- | --- |
| Overview | Operational Dashboard Hero and committed operational signals | Four KPI cells use shared divider grid **inside existing** Operational Signal Overview shell, with no extra card shell | Dashboard four operational workspace views | **Align** bounded lazy KPI content only under #1087; preserve #911/#923 shell |
| Inventory | Shared Hero / committed snapshot context | Overview **Fleet Inventory Posture** external intro + grouped three-metric estate shell; **Inventory Assets** intro + Kubernetes-style **Registry Asset Catalog** panel; resource pages retain Operational Posture intro + grouped resource metrics | Shared Projects/Repositories/Artifacts navigation cards; bounded resource inventory tables, HTMX filters and 5-row pagination | **Align** #946 follow-up to the accepted grouped Registry summary and Kubernetes catalog family without provider/data changes |
| Security | Shared Hero / Security Sync / committed scan evidence | External **Security Snapshot** intro + shared grouped four-metric posture grid, independently scoped for Vulnerabilities / Supply Chain | Small content-tabs family for Supply Chain; shared vulnerability/evidence registry and 5-row footer | **Align** summary composition under #1087; preserve #948 scanner semantics |
| Runtime Usage | Shared Hero / committed correlation snapshot | External **Runtime Correlation** intro + four-cell grouped committed correlation grid | Runtime Bindings section intro and bounded table; committed correlation, 5-row footer | **Align** summary composition under #1087, retain #897 correlation semantics |
| Governance | Shared Hero / Governance Sync / committed policy evidence | External **Governance Coverage** intro with one grouped operational estate shell and four evidence metrics; original Committed/Observed status badges retained | External Governance Evidence intro; standard URL/HTMX content tabs for Policies/Replication; 5-row footer | **Align** to Kubernetes Tenant Estate's shared posture-grid archetype under #950 |
| Analytics | Shared Hero / committed analytical materialization | Overview owns **Registry Analytical Posture** four-cell grouped summary with Review/Unavailable/Ready labels; detail views own focused evidence | Eight page-level Integrated Workspace Tabs (Overview + seven dedicated domains); existing bounded HTMX summary/section fragments | **Align** #1097 with Kubernetes Analytics level-3 navigation under #747/#748, preserve #899/#952 committed authority |

#### Component and composition rules applied in this audit

- **Current Artifact Registry metric summary standard:** a plain
  `section_intro` outside an existing shared operational shell containing
  `resource_posture_grid` with thin dividers, one responsive column on mobile,
  two on tablet and four at desktop. **Overview** keeps its already-authoritative
  `operational_signal_overview` shell; its lazy KPI projection is the grid body
  with no new nested shell. Inventory stays grouped within its existing
  `operational_section_card`; Security, Runtime, Governance, and Analytics
  use the same shared grouped presentation. Governance/Analytics retain their
  committed status labels. No extra card borders within metric cells. The
  Inventory Overview Fleet posture now uses the same grouped grid for three
  committed metrics; the Inventory resource-detail pages retain their grouped
  four-metric posture.
- The **Inventory Operational Posture** on resource pages and **Fleet Inventory
  Posture** on the Inventory Overview are coordinated evidence panels using the
  approved `operational_section_card` and `posture_grid`, retaining provider,
  snapshot exception, and visibility semantics. The Inventory Overview catalog
  follows the Kubernetes asset navigation shell with a section intro,
  `Registry Asset Catalog` header/badge, and shared destination cards. This
  intentionally revises #946's earlier flat-catalog rule after explicit human
  visual feedback; do not change Object Storage or introduce new wrappers in
  unrelated Registry pages. The Overview dashboard continues using the
  canonical Operational Dashboard composition.
- **Navigation follows interaction scope**, not cosmetic uniformity. The
  two-view Governance and closely related Supply Chain content use
  `content_tabs.render_links`. Artifact Registry Analytics now follows
  Kubernetes Analytics' server-owned **page-level Integrated Workspace Tabs**
  with Overview plus seven analytical domains (#1097), removing its previous
  in-card `framed_workspace_tabs` and retaining individual lazy bounded HTMX
  analytics projections. These are distinct from subordinate content tabs and
  preserve capability-level sidebar and keyboard/navigation semantics.
- Use shared Hero, loading/empty/error, filters, tables, labels and default
  five-row paginated footer in each owning workspace; never replace provider
  semantics with generic optimistic states. Icons and badges convey meaning,
  not decorative visual repetition. Avoid creating new page-local CSS/JS,
  tokens, wrappers or one-off card families.

**Implementation separation:** #950 owns Governance Coverage composition;
#1087 owns the follow-up **entire Registry** grouped-summary consistency
implementation (Overview, Security, Runtime and Analytics), its verifier and
cross-page audit. Inventory's existing grouped composition remains unchanged. Existing #911, #931, #948, #897 and
#899 remain authoritative for their specific capability data or backend
behaviors. Work is grouped only for fast DevContainer review at
`kaori/review/staging-uat`; no CI/CD Full Admission, deployment, staging
promotion or main promotion occurs without explicit approval.

**Developer / human Visual QA:** verify summary headings and shared grouped
metric cells on all six Registry pages, original Overview shell and Inventory
posture header, no double borders, responsive 1/2/4-column grids,
Violet light/dark contrasts, meaningful per-metric badges, Security
Vulnerabilities/Supply Chain view switching, Policies/Replication HTMX,
Analytics framed seven-domain URL transitions, 5-row pagination, and zero/
nonzero committed evidence. A static Jinja source review is **not** browser
Visual QA or human acceptance.

### Governance Coverage and Evidence layout (#950 DevContainer follow-up)

The Governance evidence area now follows the established Security/Supply
Chain section hierarchy. Two **plain section-intro headings outside their
card shells** provide operator context:

- **Governance Coverage** — following further human feedback and the existing
  Kubernetes Tenant Governance Scope reference, one shared
  `operational_section_card` encloses a `resource_posture_grid` of four
  coherent estate-level evidence metrics. Icons summarize category/tone;
  the optional original Committed/Observed/Partial/Not Collected label is
  retained using the existing status-indicator component. The section intro
  stays **outside** the grouped shell. There are no nested independent cards;
  all values, evidence statuses and provider-authoritative meanings remain
  unchanged. This grouped archetype is purpose-specific, not a global rule
  for Registry Security, Runtime or Analytics.
- **Governance Evidence** — Policies/Replication remain in one canonical
  section card with `content_tabs.render_links` (embedded, server/URL-owned
  mode), matching Security Supply Chain. Tab labels remain **without counts**.
  Following explicit human clarification, each tab owns the **complete canonical
  KAORI table workspace**, not an isolated bare table: shared
  `table_ui.inventory_block_header` with Policy/Replication title, evidence
  description, count metadata badge, Clear Filters action and a shared
  loading bar; `registry.filter_form` with Search/Provider and tab-specific
  Retention+Immutability or Replication State; then the full-width shared
  `components/table.html` table, semantic status labels, canonical
  `states/_empty_state.html` fallback and `registry.footer` pagination.
  The previous redundant freeform Policy Evidence / Resilience Evidence
  headers do not return. Search and filters operate against committed
  provider-neutral rows before the existing sequence pagination; Policy/Retention/
  Immutability/Replication Coverage in the summary still uses the unfiltered
  estate totals. The current tab and active filters round-trip through GET,
  HTMX updates, page size changes, Governance Sync and terminal refresh.
  Switching tabs intentionally opens that tab's unfiltered page 1.
  HTMX targets/selects only `#artifact-registry-governance-registry` and
  canonical pagination remains 5/10/25/50 (default 5), without new live
  provider requests or policy mutation.

This replaces Governance's previous framed tab treatment without introducing
another UI pattern, altering provider authority, changing content-tab semantics
or making live Registry API requests. Default pagination remains 5.
DevContainer Visual QA should verify external headings, grouped-grid dividers,
status badges and icon tones, active/inactive tab contrast, light/dark and mobile
layouts, Policies/
Replication transitions, back/forward navigation, sync completion refresh,
and the shared pagination footer. CI/CD, Full Admission, staging/UAT and
promotion remain **HOLD**.

### Entire Artifact Registry grouped summary adoption (#1087, latest feedback)

Human feedback explicitly requires the selected Kubernetes Tenant Estate
**grouped metric-grid pattern across the entire Artifact Registry**, not only
Governance. This supersedes the earlier proposal to keep independent summary
cards on Security, Runtime and Analytics. The six-page audit has been updated
accordingly; page-specific navigation and provider authority do **not** change.

- **Overview:** use the existing `operational_signal_overview.render` with a
  new backward-compatible `body_classes='p-5'` default, requested as
  `body_classes='p-0'` by Registry. Bounded/lazy KPI rows render through the
  existing `resource_posture_grid` within this shell—do **not** nest another
  `operational_section_card`. Retain four dashboard tabs, provider scope,
  freshness/status context and the lazy HTMX KPI endpoint.
- **Inventory:** the existing `operational_section_card` +
  `resource_posture_grid` meets the reference and remains unchanged.
- **Security:** both Vulnerabilities and Supply Chain summary scopes now
  populate four grouped metric cells in `operational_section_card`. Display
  values retain original committed source and descriptions; category tones are
  warnings for observed findings/coverage gaps, **neutral/informational for
  zero** so absent scans are never inferred clean. Native Security Snapshot,
  filtered evidence and scanning rules remain authoritative.
- **Runtime:** four grouped metric cells retain digest-vs-tag confidence;
  Tag Matched is warning when present, Security Exposed is critical when
  present. Zero/unknown correlation is not an inferred clean runtime posture.
  Committed correlation/read-only links and identity evidence are unchanged.
- **Governance:** uses #950's prior grouped four-metric posture shell with
  original Committed/Observed/Partial/Not Collected status labels.
- **Analytics:** the four existing analytical values and the original
  Review/Unavailable/Ready status labels are projected into the shared
  `resource_posture_grid` **only on Analytics Overview**. Detail pages use
  focused lazy HTMX sections under canonical eight-view page-level navigation
  (#1097), without a second framed tab bar.

All six areas reuse **existing** icon/tone/divider geometry; only a
backward-compatible optional Overview shell-body argument was added.
No new provider request, authentication, database change, job dispatch,
scanner, backend metric computation or inventory/analytics authoritative
source is involved. Tests follow the existing contract and Operational
Dashboard verifier; local browser Visual QA must verify responsive
one/two/four-cell layout, light/dark mode, long labels, loading-to-evidence
updates, status tone semantics, tabs and 5-row Registry tables. CI/CD
admission, staging/UAT and main promotion remain HOLD.

### Governance Coverage grouped posture implementation (#950 latest human feedback)

The Kubernetes Tenant Governance Scope screenshot is the approved reference
for **one estate-level grouped evidence summary**: a plain outer section
heading, a standard `operational_section_card` with an icon-accented
header, and a `resource_posture_grid` body with thin dividers between
metric cells. Registry Governance Coverage now reuses these exact shared
components rather than introducing a new metric-card CSS pattern.

The existing Governance presenter still provides exactly four committed
posture records in Policy/Retention/Immutability/Replication order. All
`label`, `value`, `detail`, `tone`, and `status_label` fields remain
authoritative. An optional `status_labels=none` argument extends the
existing posture-grid component so this Registry view can display the same
canonical Committed/Observed badges without changing the default five-metric
Tenant Estate rendering. Badge semantics and warning/unknown tone are never
inferred from metric counts by the UI. No collector, provider, data contract,
JobExecution, HTMX, pagination or Registry tab behavior changes.

The shared grouped grid is responsive: one cell per row on narrow widths,
two from `sm`, four at `xl` for Governance; values and supporting descriptions
wrap within their cells. Human Visual QA must verify the four-status matrix,
dark/light contrast, viewport width, no extra nested card border, long
provider details, and Policies/Replication navigation. CI/CD and deployments
remain HOLD.

## Vulnerability Findings Registry: compact list and committed detail (#948)

The Vulnerability Findings workspace presents its committed Security Evidence
interpretation inline beside the existing `section_intro` heading, not as a
full-width severity-colored callout. It uses the canonical
`table_label.status_label` and accessible, pointer/keyboard/touch-enabled
`info_tip` to retain the current collection, scan-coverage and refresh-state
explanations without consuming a separate panel. A fully collected finding
set is labeled informational **Committed Evidence** regardless of
whether it contains Critical/High CVEs: security severity remains visible in
the snapshot metrics and per-finding rows, not inferred from evidence
provenance. Not-collected, failed-refresh, missing-scan and partial-coverage
states retain their distinct semantic labels and tones. A filtered or
zero-result view never proves the Registry estate is fully scanned. The
bounded HTMX Vulnerability Registry retains canonical 5-row pagination,
filters and source/permission scope.

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

## Analytics Controls & Data Readiness (#1099)

The Registry Analytics Overview and all seven focused analytics pages use the
approved Kubernetes Analytics **Controls & Data Readiness** composition.
Overview uses the canonical **Analytics Overview** eyebrow, while focused
domain pages use their own page title. The Registry source card uses the
same semantic status-dot/title/badge hierarchy as the K8s Metrics Source
Status card without claiming that Registry source eligibility proves live
Metrics Source query readiness.
Their authoritative read-only source/commit readiness comes from
`build_registry_analytics_readiness`, which reads eligible Registry providers,
the latest ready materialized snapshot per eligible provider, snapshot expiry,
existing JobPolicy (without creating it in GET), and canonical JobExecution.
Committed-data readiness, eligibility, active collection, last failed attempt,
and scheduled collection are separate states; a failed newer worker run does
not discard previous committed evidence.

Following human review, Registry and Kubernetes Analytics **share the
exact same** `analytics/components/_controls_readiness.html` frame and
snapshot-card macros: one header/eyebrow/description, header loading bar,
two-column scope controls, two-column source/snapshot readiness, and
contextual warnings. The existing K8s capacity `controls_readiness` macro
delegates to this shared shell without changing its public signature,
cluster/time-range controls, Metrics Source-specific card, or snapshot
interpretation. Registry renders the shared source card with its own genuine
provider/snapshot evidence and genuine dropdown controls:
**Registry** (all active Registry integrations or one named provider) and
**Time Range**, matching K8s Overview wording and order: Last 1 Hour,
Last 6 Hours, Last 12 Hours, Last 24 Hours, Last 7 Days, Last 30 Days,
and Last 60 Days. The default is **Last 24 Hours** like K8s; an additional
**Latest Snapshot (Any Age)** choice retains explicit compatibility with
legacy `snapshot_window=current` bookmarks. The existing HTMX filter and
loading convention applies to all committed analytical summaries and
domain sections before aggregation/pagination. K8s time ranges describe
materialized provider metrics, but Registry currently keeps only the most
recent materialized snapshot per provider: here Time Range filters its
`generated_at` timestamp, **not historical provider telemetry**. No
unsupported historical trend is invented. When snapshots exist outside the selected lookback,
readiness reports **No Snapshots in Window** rather than incorrectly claiming
Registry analytics were never collected. Alerts source and record filters
preserve the selected provider/window through pagination and browser history.
Neither domain introduces a false Metrics Source readiness claim for Registry.

The Registry panel **does not contain manual Collect/Configure buttons**.
As in K8s Analytics, a bounded HTMX GET to
`/artifact-registry/analytics/materialization/resolve` checks the committed
snapshot freshness and dispatches the existing registered
`artifact_registry.analytics.materialize` job only when eligible evidence is
missing/expired, no active job exists, and the latest attempt is outside a
five-minute retry cooldown. This routes to the existing `analytics-batch`
worker through `dispatch_registered_job(trigger_type='on_demand')` with
canonical JobExecution deduplication and a registered-worker preflight.
The top-level page GET stays a fast committed-state shell; the background
request may schedule work but never performs synchronous live provider queries.
JobPolicy scheduling continues independently, with no write-on-page-read
policy creation. UI loading and scoped JobExecution progress now appear in the **shared
Controls & Data Readiness header** using its original loading bar and
an optional header-content slot (Kubernetes does not change behavior).
Previously duplicated worker progress below the source/snapshot cards is
removed. Resolver requests retain the selected Registry provider/window,
but canonical on-demand dispatch assesses **global fleet readiness** because
the existing worker collects fleet-wide. Terminal page refresh reads the
committed scoped snapshots; a later failed job retains old evidence.
Queue/preflight errors are displayed as warnings, never as successful refresh.
Manual execution remains available through existing Platform Operations Jobs
rather than a second domain-specific collection button.

## Analytics Fast-Shell Contract

Artifact Registry Analytics uses the same bounded delivery principle as the canonical operational dashboard:

```text
GET /artifact-registry/analytics
  → fast shell
  → lazy Analytics Summary
  → lazy active workspace section
```

Overview is the canonical `/artifact-registry/analytics` landing route and
presents the existing lazy materialized analytical summary, followed by seven
bounded navigation destinations. Page-level Integrated Workspace Tabs use the
existing `artifact_registry_analytics` capability-view catalog and same layout
owner as Kubernetes Analytics. Each of Growth, Capacity, Usage, Risk, Governance,
Alerts & Anomalies and Insights has a dedicated canonical
`/artifact-registry/analytics/<domain>` route. Each deep route shares the fast
shell and lazy loads only its active committed analytical section; it does not
repeat the Overview estate summary. The legacy `?tab=<domain>` bookmark shape
redirects to the corresponding route and preserves bounded Alerts search,
severity, state, source and pagination query parameters. Alerts HTMX table
updates push its canonical page URL. No additional materialization models,
provider read paths, RBAC definitions, alert collection or central Intelligence
recommendation lifecycle are introduced.

## Shared Analytics Section Loading (#1106)

Artifact Registry Overview and its seven dedicated analytical routes reuse
the exact K8s `analytics/components/_section_load_tracker.html` geometry and
the shared `js/analytics/section_load_tracker.js` runtime. Overview tracks
its actual lazy committed Summary fragment; a focused route tracks only its
active evidence fragment. Each fragment owns its loaded/failed state across
outerHTML swaps. The tracker is shown after Hero and counts **requested
HTMX sections**, not invisible routes or Celery work items. The shared
controls header continues to show the independent filter loading bar and
JobExecution collection progress. A materialization-status refresh may
reload the page once the worker commits its evidence; the next section
request is counted afresh. The old K8s handler remains available as a
compatibility hook.

For a new Analytics domain, add `data-analytics-section-tracker-root` on
the page wrapper, invoke the shared macro once after Hero, mark only actual
lazy request nodes with `data-analytics-lazy-section="true"`, and include
the shared controller asset once. Mark a full-fragment replacement with
`data-analytics-load-state="loaded"` and preserve its stable element ID
so the tracker can resolve the completed element after HTMX outerHTML
swaps. Do not create a new tracker JavaScript controller per domain.

## Operational UI Contract

Normal Artifact Registry pages read committed KAORI state. Provider calls are worker-owned and never occur
in normal page rendering.

Every asynchronous operation uses the canonical Job Execution lifecycle, shared progress contract,
worker-registration preflight, audit trail, and scheduler policy. Provider-specific collectors remain behind
provider-neutral Artifact Registry contracts.
