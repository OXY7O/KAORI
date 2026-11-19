# Artifact Registry Security — Overview and focused workspaces

## Authority and scope

- Parent capability: #896. Bounded visual/route implementation: #4468.
- Existing sync and finding-state governance: #948, #915.
- Reference presentation: the approved Artifact Registry Inventory Overview and KAORI shared design patterns (#946, #4455, #572, #753).
- Operational source of truth: **committed KAORI Registry security evidence**, not a live Harbor/scanner query. External scanner/provider remains authoritative for detection, signature and SBOM evidence.

## Navigation and ownership

| Route | Endpoint | Purpose |
| --- | --- | --- |
| `/artifact-registry/security` | `artifact_registry.security_overview` | Read-only Security Overview landing |
| `/artifact-registry/security/vulnerabilities` | `artifact_registry.security` | Existing Vulnerabilities workspace and canonical finding filters |
| `/artifact-registry/security/supply-chain` | `artifact_registry.security_supply_chain` | Existing Supply Chain workspace with capability and evidence subviews |

The sidebar Security capability links to the Overview. The shared `workspace_navigation_catalog.py` now owns the three top tabs **Overview → Vulnerabilities → Supply Chain**, rendered by `layouts/app.html` via `components/workspace_tabs.html`. Do **not** duplicate tab markup in Security templates.

Existing internal `url_for('artifact_registry.security')` and `url_for('artifact_registry.security_supply_chain')` continue to target their original focused workspaces; their route **paths** may differ from historic Security entry URLs. Every route uses `artifact_registry.view` authorization. The Overview `source_id` is validated through the existing fail-closed Security source resolver; Overview catalog links preserve the validated ID.

## Overview composition

1. KAORI Violet shared Hero: source/critical/affected context, source-qualified risk posture, direct action to Vulnerabilities.
2. Shared **Security Evidence Snapshot** context bar: freshness, eligible Registry scope, usable scan coverage and exceptions; a successful job is **not** equivalent to current committed scan evidence.
3. **Security Workspaces** catalog: two compact shared `workspace_link_card` destinations, derived critical-finding and signature/SBOM coverage-gap counts.
4. **Security Evidence Posture**: shared `operational_section_card`, `N Indicators` metadata label, and four compact `resource_posture_grid` metrics for critical, high, affected artifact digests and correlated runtime bindings.

The Overview projection reuses `_registered_sources`, `_providers`, `_security_scope_evidence`, `_security_scope_labels`, `_security_snapshot_context`, and `_security_posture`. Counts and tones use committed-scoped evidence only. When no current successful scan evidence is present, metric tones are **Unknown** rather than inferred Healthy from zero counts. This does not certify absent findings, non-exposure or supplier compliance. Unsupported signatures/SBOM are not presented as verified.

When providers are unregistered or committed inventory is not ready, retain the existing shared provider/inventory blocked states and standard corrective navigation.

## Security Evidence Operations copy

On focused Vulnerabilities and Supply Chain pages, `_security_sync_live_state.html` displays a **single concise line** combining a source-qualified queued/syncing/failed/not-collected/ready state with **read-only; no provider scans**. It must wrap naturally on narrow viewports; never truncate or use `nowrap`. Progress, polling, disable-duplicate execution, Jobs & Executions authority, and the canonical `artifact_registry.security.sync` job remain intact.

### Security Sync Guide and Supply Chain detail readability (Human Visual UAT #4590)

In **Security Evidence Operations**, the HTMX-refreshable live-state header
renders the existing `info_tip.render(..., variant='guide')` immediately after
the status indicator, matching the approved Governance Evidence Operations
pattern. The accessible Guide explains read-only committed scanner/supply-chain
and runtime correlation evidence, provider authority, the eligible-source
`JobExecution` sync boundary versus page-local filters, and the need to review
missing/stale/partial/unavailable/unsupported evidence. Opening a read-only
workspace or modal never triggers live provider reads or scans; the explicit
Security Sync action retains its existing authorization and execution semantics.
Preserve status polling, active progress, `compact_helper`, and natural wrapping.

The **Provider Capability** and **Artifact Evidence** View More modals keep their
existing evidence cards and `operational_callout` components. The descriptions
for **Committed Security Capability Scope**, **Provider Evidence Boundary**, and
**Evidence Interpretation** use concise one-line desktop microcopy without
`whitespace-nowrap` or information truncation on mobile. The provider remains
authoritative for capability detection, signatures and SBOM availability.
Provider observations do not constitute KAORI trust-policy verification;
capability states must not be inferred or fabricated. The modal is read-only,
while full immutable digests, capability/scan states and timestamps remain in
their normal evidence fields.

## Security Evidence Summary and finding-table consistency (Human Visual UAT #4468)

Both focused Security tabs, **Vulnerabilities** and **Supply Chain**, retain their four
committed, domain-specific Security Evidence Summary metrics. The existing shared
`table_label.metadata_label(security_metrics|length ~ ' Indicators', icon='layout-grid')`
is displayed in the `operational_section_card` header as a **static** `4 Indicators`
badge, not an interactive Guide. Do not conflate a missing scan with zero findings
or a signed artifact with evaluated trust.

The Vulnerability Registry continues to use KAORI `table_ui` / `table_registry`
visual and HTMX contracts, with the existing six columns and 68rem responsive
minimum width. Prefer the shared `table_ui.title_cell` supporting-content slot
to group severity beneath the CVE identity and freshness beneath the provider
source. Keep artifact/project hierarchy and installed package/fix context together,
display singular `1 Binding` versus plural `N Bindings`, and use the shared
`table_ui.action_grid_classes(columns=1)` for aligned `View More` / conditional
`Impact` actions. The grouped styling must not change evidence availability,
severity semantics, scan freshness, provider provenance, modal actions, canonical
pagination (default five), keyboard focus, filters or latest-request-wins HTMX
behavior. On narrower viewports the existing horizontal scroll must preserve
access to all columns and actions; do not clip or mask evidence.

## Compact Security metrics and CVE Runtime Impact drill-down (Human UAT #4468 / #2603)

The Vulnerabilities and Supply Chain `Security Evidence Summary` cards retain the
same committed metric values, scope predicates, status semantics, and four-column
shared posture grid. Each supporting description must be concise enough for a
single desktop line in its metric card where the viewport permits. Use natural
responsive wrapping rather than `nowrap` or truncating evidence. Provider
signature presence is not a verified signature/trust policy, and unknown runtime
correlation must not be inferred safe from a zero.

The read-only exact-CVE drill-down uses the same shared two-column Violet Hero
composition as Registry Runtime Overview: `page_hero.intro` occupies the primary
column and `page_hero.context_card` displays actual committed correlation
readiness, source-qualified affected digests, runtime binding counts, and the
existing back-to-Vulnerabilities action in the secondary column. Do not leave the
second column blank or place a stretched standalone action in the first column.
The topbar breadcrumb resolves `artifact_registry.security_cve_impact` to
**CVE Impact**, not a default Overview label.

The shared `snapshot_context_bar` must use concise displayed scope/coverage
labels to avoid clipping on desktop; exact Registry/Kubernetes scope and readiness
authority remain in the committed correlation model and displayed explanatory
copy. `Not Qualified` must remain distinguishable from `Current`. Reuse the
existing shared `table_ui.block_classes()` card surface for the two paginated
evidence tables. Preserve full digest identities, source and scan timestamps,
CVE/severity/fix evidence, digest-vs-tag binding confidence, canonical footers,
RBAC, HTMX, and direct Runtime Usage drill-down. The tables are read-only
committed evidence, not authoritative Application/Team ownership.

## Exact-CVE evidence tables: multi-record presentation (Human UAT #2603)

The two red-marked `CVE Runtime Impact` sections are **one-to-many committed
datasets**, even when a sample CVE happens to have only one row. A CVE may
appear across several Registry artifacts, projects, sources, and packages;
each affected digest can have several independent Kubernetes runtime bindings.
Therefore both sections remain **canonical KAORI tables**, not static cards or
single-record fact sheets. The read model retains two independently paginated
server-side queries, with a default of five rows and existing choices of
5/10/25/50. The tables must not silently show only a sample row.

Both sections use one `table_ui.block_classes()` surface each, with a shared
`table_ui.inventory_block_header` that owns its icon, descriptive hierarchy,
loading indicator, and a source-counted `N Findings` or `N Bindings` metadata
badge. Do not nest an extra colored card or unowned standalone heading around
the table. Reuse `table_ui.table_classes`, column/body/row/cell classes,
accessible captions, horizontal scrolling and the canonical `registry.footer`
with independent `finding_page`/`runtime_page` route identity and page-size
controls. The embedded `components/states/_empty_state.html` is the source of
consistent empty states, with explicit **unknown/unverified** language when
correlation evidence is not current.

The scanner evidence table presents Registry source/artifact/digest provenance,
package/installed version, severity, fix version, last observed scan and
Runtime Usage drill-down. The runtime table presents cluster/namespace,
workload/pod/container, provider-neutral match confidence, observation time
and Runtime Usage drill-down. Digest previews are compact in the multi-record
table, while the entire immutable value remains available through
the canonical keyboard-operable Copy Digest action and the full-value title.
A digest match carries stronger evidence than a mutable tag/reference.
No runtime rows never means the CVE or the application estate is safe;
external provider findings and committed KAORI correlation remain authoritative.
This is a view-only redesign: no query, provider, worker, RBAC or schema change.

## CVE Impact section hierarchy and independent filtering (Human UAT #2603)

The exact-CVE page has one `CVE Evidence` section heading and a shared
`workspace_tabs.render_query_tabs` tab strip using the **same query-backed
HTMX tab geometry** as the approved Kubernetes Tenant Membership Registry.
The tabs are **Affected Artifact Evidence** and **Kubernetes Runtime Exposure**.
Each tab displays only its own canonical table card; both tables must never
stack or render simultaneously in the DOM. The selected tab is the validated
URL parameter `evidence_tab=findings|runtime`, defaulting to findings for
missing/invalid values. Normal navigation works without JavaScript; HTMX
replaces only the `#artifact-registry-cve-evidence-workspace` container with
inherited `hx-select`, preserving the Hero and correlation snapshot.

Each active table card still owns its `inventory_block_header` (icon,
domain evidence title, filtered result count badge and loading bar), with no
extra nested colored surface or independent second section heading. Shared
`table_ui` column/body/cell styles and canonical registry filtering, empty
states, pagination and runtime actions remain authoritative. The content
hierarchy prioritizes asset/workload identity, then a compact digest preview
with the existing accessible Copy Digest action or pod/container metadata,
followed by source-qualified severity/freshness or correlation badges.
Retain the full immutable digest as the hidden clipboard source and full-value
title, with proportional columns and responsive horizontal scrolling.

Both evidence tables can contain many records. Each therefore exposes the
canonical `table_registry.filter_form` and `clear_filters_link`, not a static
textbox or page-local HTMX pattern. The form macro accepts an optional
`path_params` argument for routes with required path identity (here:
`/artifact-registry/security/cve/<cve_id>/impact`). Default form behavior for
routes without path variables is unchanged. The shared form retains its
latest-request-wins `hx-sync`, shared workspace-owned `hx-target` /
`hx-select` (keeping query-backed tab URLs synchronized), accessible label,
debounced input, and push-URL behavior.

The **Affected Artifacts** table supports a literal case-insensitive text
search over Registry source, repository/project, immutable digest, package and
installed version, plus a severity selector. The **Runtime Exposure** table
supports literal case-insensitive search over cluster, namespace, workload,
pod, container and image reference, plus a **Digest Match / Other Reference**
selector. Filters are applied in the committed read model **before**
pagination, never as client-side filtering of just the visible five records.
The exact CVE, last-good scanner authority and source-qualified bound
artifact set remain fixed. A filtered-out finding or binding must **not**
change the overall Hero/correlation evidence counts, imply no risk, or
change the provider authority. Card result badges reflect filtered table
totals and the shared footer reflects the filtered result window.

URL-backed state is independent: `evidence_tab` selects the owning
view without changing CVE identity, while `finding_q`, `finding_severity`,
`finding_page`, `finding_per_page` and `runtime_q`, `runtime_match`,
`runtime_page`, `runtime_per_page` preserve both tables' respective state.
Both tab destinations carry all filter/page/Rows parameters so switching
tabs restores the previous operator context. Every filter form, Clear Filters
link and pagination request also retains the active `evidence_tab`.
Submitting or clearing one table
resets only that table's page to one, while preserving the other table's
filters, page, and page size. Both table footers retain the counterpart
state and the original allowed 5/10/25/50 page-size options; the default
remains five rows. Server queries escape LIKE wildcards, cap free text to
128 characters, and enforce the allowed selector values. No live provider
query, scan dispatch, RBAC change, or unsanctioned new UI primitive.

## Compact CVE correlation snapshot and evidence identity fields (Human UAT #2603)

The exact-CVE Runtime Correlation Evidence snapshot uses concise committed-copy
(`Committed Registry × Kubernetes correlation.`) to keep the four-column
desktop snapshot readable without forcing `whitespace-nowrap` on narrow
screens or hiding actual readiness/provenance. The authoritative status,
timestamp, source scope, coverage and exception indicators are unchanged.

Within the canonical five-column Affected Artifact Evidence table, retain
the `Digest` semantic label/value pair (`dl/dt/dd`) in a single compact
metadata row. Show a bounded prefix-and-suffix SHA preview with the full
immutable digest retained in its `title` for inspection. Follow it with
a compact text-only **Copy** action, with no icon, border or filled
button chrome, using the existing global `app/static/js/clipboard.js`
delegated `data-kaori-copy-root`, `data-kaori-copy-source`, and
`data-kaori-copy-button` contract. Keep the semantic `button type="button"`
for keyboard accessibility, but style it as a subtle inline text affordance
with Violet hover/focus and dark-mode contrast. The hidden copy-source
contains the **entire exact digest** (not the ellipsized preview); shared
feedback changes the action label to `Copied` after success. Do not render
an expanded disclosure, icon, duplicate full-length digest block, or separate
outlined action in table rows. This remains read-only client-side copy with
no provider call, extra script, or mutation.
The runtime Workload / Pod cell keeps `Pod` and `Container` as aligned
semantic rows beneath the workload identity.

Following the approved table-header action-group standard
(`docs/design/components/TABLE_AND_LABEL.md` §11), both tabs render
conditional `table_registry.clear_filters_link` inside the existing
`inventory_block_header(..., header_actions=...)`, **not** alongside
filter fields. Search and facet inputs remain full-width, content-aware peers.
The link resets only the active tab's filters and page while preserving its
Rows, `evidence_tab`, and the other tab's search/page/Rows state. Filter,
Clear Filters and footer requests replace the shared CVE evidence workspace
so query-backed tab links cannot retain stale state. Shared Violet light/dark,
focus, responsive and keyboard semantics remain authoritative.

## CVE Runtime Impact correlation advisory (Visual UAT #4750)

When `impact.evidence_ready` is false, the exact-CVE impact page displays a
single read-only **correlation advisory** between the standard Runtime
Correlation Evidence snapshot and the CVE Evidence workspace. Compose it with
`components/operational_callout.html` (`variant='neutral'`) rather than a
page-local bordered paragraph strip. The existing callout owns the semantic
icon, title, spacing and contrast; the page provides the **actual**
`impact.correlation.status/tone` badge, concise interpretation and a short
source/Runtime Usage handoff. Unknown, stale or changed Kubernetes correlation
means **impact completeness is not verified**, never that no applications
are affected. Readiness remains owned by the committed Registry × Kubernetes
correlation source; opening this page or advisory must not trigger a provider
query, scanner execution or correlation refresh. Keep the approved Hero,
snapshot bar, source-qualified five-row registries and their existing filters,
pagination and source-permission boundaries unchanged.

## QA and admission

- Exact-commit djlint and Ruff check/format on updated templates and Python files.
- Focused Security source contract and navigation contract, existing RBAC/scope regression, and current dashboard verifier where applicable.
- Browser Visual UAT of 1440/1280/mobile widths in light/dark, keyboard focus and tab navigation, active source/blocked/no evidence/stale/partial evidence, and sync status transition. Record screenshots under issue #4468.
- The temporary `kaori/review/staging-uat` holding integration is **not** official Full Admission; `kaori/staging`, main, deployment and release remain gated by Human Acceptance.
