# Security Posture — cross-domain committed evidence

**Architecture authority:** #721 (Security Posture), #900 (Intelligence boundary), #747/#748 (Sidebar v2), #2600 (CVE-to-Application plan).  
**Initial implementation:** #2610. Pre-UAT hardening: #2613.

## Ownership

Security Posture is an Assurance workspace that **consumes** source-qualified committed evidence. It is not a second scanner, CMDB, secret store, SIEM, advisory service, recommendation engine or generic vulnerability database.

- **Artifact Registry** owns scanner CVE, package, version, digest and scan generation (initial source).
- **Kubernetes / Registry runtime correlation** owns observed workload bindings, source identity and signed input-generation readiness.
- **Central Intelligence** owns recommendation/alert/accepted-risk lifecycle. **Reports** owns publication.
- Later Security workstreams may add Source Control, Services/Team, Vault/PKI, hosts, Network and policy exceptions only after approved source and evidence contracts are available.

## Routes / navigation

- `/security/` → **Security → Overview**: approved Governance-style Violet Hero and committed source context; grouped Security Snapshot; one Exposure & Runtime Evidence analysis; four integrated perspectives. The **Exposure Analysis** panel presents **Finding Highlights**: three severity-ordered qualified CVEs and compact source-wide counters, not a full registry. `Open Findings` owns detailed search, filters, loading, pagination and investigation. The canonical four tab keys and their Security-specific labels remain unchanged (see #4711).
- `/security/findings` → **Security → Findings**: full source-backed grouped CVE registry with the same approved Governance-style Hero, source-qualified Evidence Qualification, canonical header/Guide/loading bar, Search CVE and Severity filters, read-only `Refresh View`, 5/10/25/50 server pagination, clear-filter and empty states, plus exact-CVE impact links. This is the full investigation surface (#4772); the page does not initiate scans or provider calls.
- `Artifact Registry → Security` continues as authoritative source-domain workspace. Exact CVE rows link to its existing `/artifact-registry/security/cve/<CVE>/impact` drill-down; Security does **not** duplicate that detail view.
- The **Assurance** sidebar contains a two-level Security parent with only real route-backed Overview/Findings children. Planned capabilities remain hidden; no new renderer/CSS family.

## Security Assurance perspective tabs — Human Visual UAT #4711

The non-Exposure perspectives reuse existing `operational_section_card`,
`action_button.classes`, and `info_tip.render(..., variant='guide')`:
- **Assets & Impact**: two equal-height source-qualified digest/runtime
  readiness cards, footer-aligned owning-domain links and a compact persistent
  interpretation boundary. An individually Ready runtime generation does not
  make scanner evidence fresh.
- **Findings & Investigation**: one bounded summary of distinct CVEs, affected
  digests and observed container bindings, plus a single primary Findings
  handoff and permission-filtered Intelligence link. When correlation is not
  Ready, binding totals display **Unknown**, never fabricated zero.
- **Evidence & Sources**: two balanced provider-authority cards and an
  integrated publication boundary. The `Open Reports` link remains gated by
  `can_view_reports`; a read-only boundary stays visible without that permission.

Security Snapshot also exposes a shared **Scanner Evidence Freshness Guide** next to its source-derived scanner-status badge. It explains the 24-hour window for the oldest qualified scan, why an unchanged CVE count is not evidence that a rescanning event did not happen, and why Security Sync / Findings Refresh View / Runtime Correlation are different operations. Keep scanner Stale and provenance text persistent outside the Guide.

All three tabs have a canonical header-level **Guide** explaining the source
ownership and evidence limitations. Guides are supplemental, never the sole
location of unknown/stale warnings or permission requirements. The original
four-tab URL keys and scoped source RBAC remain unchanged; full table and HTMX
loading now belong exclusively to the Findings page.

## Security Findings Visual UAT polish — #4772

The **Finding Highlights** region on Overview reuses three compact
`operational_metric_card.render(..., compact=true)` cards for distinct CVEs,
affected digests, and source-qualified runtime correlation, rather than
page-local flat boxes. Its first three observed CVEs use the existing
`table_ui.title_cell` identity (icon, CVE, supporting text, severity) within
a bordered, compact preview row, with a source-qualified `View Impact`
handoff. This is not a full table and has no filters or pagination.

The Findings page **Evidence Qualification** section uses the same compact
metric-card density for scanner coverage, committed runtime readiness, and
scanner evidence age. Their values remain independently qualified: Stale
follows the actual scan status and age, Inputs Changed is a correlation
readiness status, and neither may be displayed as fresh/all-clear without
evidence. A standard `section_intro.render` precedes the full registry,
providing the owning workspace title and description without duplicating
the table card's role. The CVE / Severity cell reuses
`table_ui.title_cell` with the shared `table_label.status_indicator_label`
instead of a page-local plain text stack. All filter, loading, pagination,
source-RBAC, HTMX and exact-CVE impact behaviors are unchanged.

## Security Sync, scanner freshness and runtime correlation

These are **three independent authorities**. `artifact_registry_security`
`JobExecution.completed_at` (Security Evidence Operations → Last Successful)
reports the **collection job's** completion, not the time a new Harbor/Trivy
vulnerability report was generated. The Registry Security collector performs
incremental collection: it compares the provider's scan completion identity,
reuses the existing `RegistryScanSnapshot` when unchanged, and records
`refreshed_report_count` versus `reused_report_count` in the job result.
A successful job with only reused reports can therefore leave
`RegistryScanSnapshot.observed_at` at its original date. The
`Security Evidence Snapshot` uses qualified committed scan timestamps, and
the Security Posture Overview checks the oldest usable scanner timestamp
against its 24-hour freshness window. **Do not replace those timestamps with
the last successful job time or silence Stale after a successful sync.**

Operator troubleshooting sequence: inspect the latest
`artifact_registry_security` JobExecution result (especially
`refreshed_report_count`, `reused_report_count`, per-source warnings, and
`report_failure_count`); check the provider's most recent scan completion
time and scan policy; run/authorize a *provider-side scan* only through the
provider's established workflow when a new scan is required, then use
`Sync Security Evidence` to commit the updated provider report to KAORI.
A UI **Refresh View** only re-reads committed KAORI table state, never
dispatches Security Sync or triggers a provider scan.

`Inputs Changed` belongs to a separate
`artifact_registry_runtime_correlation` JobExecution. The Runtime Usage
readiness check compares its last committed `input_signature` to current
Registry artifacts and Kubernetes Pod inventory and can also report a
missing generation proof. Inspect Runtime Usage prerequisites and rebuild
the committed correlation through its existing authorized job when eligible;
rerunning Security Sync or refreshing a table cannot make this status Ready.
A stale scan and an unready correlation must remain separate visible
warnings; neither condition proves that any application is unaffected.

## Read / RBAC contract

Both Security routes require `security_posture.view`; `flask seed-rbac` (in a configured **development** environment) registers the new canonical permission. **Artifact Registry source reads and source links additionally require** `artifact_registry.view`. A Security-only authorized user sees qualified unavailable/unknown states without any Registry SQL data access. Integration management and Intelligence/Reports links remain separately permission-filtered. Do not grant Registry visibility transitively from this aggregate parent.

The read model consumes only active/enabled Registry integrations with committed inventory. CVE rows come from the latest usable successful scanner snapshot per artifact. Failed scan refresh preserves last-good evidence, but freshness can become stale; a newer successful scan supersedes old findings. Deduplicated artifact and runtime binding counters are *observations* and are never a normalized application owner count. The oldest usable scanner observation and missing inventory scan coverage qualify scanner readiness; mixed partial/stale evidence is **Partial / Stale**. The canonical Runtime Correlation readiness reflects input changes and failures separately. Missing, unsupported, stale or denied sources must not be described as remediated or 'no exposure'.

The Security Overview distinct-CVE severity distribution aggregates **all
authorized latest usable scanner CVEs**. Summary counts remain independent of
the local highlight bound and of any search on the full Findings page. The
Overview's `Finding Highlights` card shows only the **first three**
severity-ordered source-qualified grouped CVEs, two relevant scope counts,
runtime-correlation readiness, and a canonical `Open Findings` handoff. It
contains **no filter form, loading bar, table header or pagination**.
A small immutable-digest/source note and a source-qualified empty state make
clear that an absent highlight is not an all-clear. The sibling
`Findings & Investigation` perspective remains a separate, governed handoff,
not a duplicate registry.

The **Findings** page owns the complete normalized CVE query workflow and
reuses `table_ui.block_classes`, `inventory_block_header`,
`table_registry.filter_form/clear_filters_link/footer`, shared loading bar,
`info_tip.render(variant='guide')`, and existing authorized CVE impact links.
Its Hero follows the Kubernetes Governance composition with Provider Authority
(Artifact Registry), Evidence Boundary (Committed) and the actual scanner
status; the context action returns to Overview. One compact
`Evidence Qualification` section presents scanner freshness and runtime
binding generation **separately**. Runtime-binding totals inside the Findings
table are shown only when the committed correlation status is `Ready`;
otherwise they are `Unknown`, never fabricated zero. Header actions are
limited to conditional Clear Filters and committed-only Refresh View.
The table uses search/severity, default five rows and sizes 5/10/25/50;
an HTMX refresh replaces **only** its own canonical table region.
No provider request, scan, remediation, new source record or claimed
application ownership is created by this read-only view.

The Security-specific Overview Hero, Security Snapshot, `section_intro`,
shared 7/5 Exposure & Runtime analysis, severity progress bars and four URL
panel keys remain unchanged. Runtime Impact still deduplicates observed
digest/reference binding identities across scoped CVE artifacts and suppresses
binding totals unless correlation is Ready. No trend chart appears until a
trustworthy historical time-series contract exists. A stale scan or a Ready
runtime binding does not independently imply safe or remediated applications.

The Findings registry differentiates **strong digest bindings** from weaker
**mutable/reference bindings** using the same correlation identity distinction
as Artifact Registry Runtime Usage. Binding counts reflect observed
container-level relationships, **not** a deduplicated count of logical
applications. No source-only 0 may be interpreted as remediated or all clear.

The initial result cannot speak for all Kubernetes workloads without matching source evidence, direct-host PHP packages, standalone Docker, network reachability, Service/Team ownership or global risk posture. No provider network I/O, mutation, new migration or background scan occurs from normal GET.

## Review and UAT

Use existing checks (no custom quality-gate framework):

```bash
ruff check app/security_posture app/bootstrap/blueprints.py app/common/navigation.py app/common/workspace_navigation.py app/common/workspace_navigation_catalog.py tests/contracts/security_posture
ruff format --check app/security_posture app/bootstrap/blueprints.py app/common/navigation.py app/common/workspace_navigation.py app/common/workspace_navigation_catalog.py tests/contracts/security_posture
djlint app/templates/security_posture/overview.html app/templates/security_posture/findings.html --check
pytest -q tests/contracts/security_posture/test_security_posture_workspace_contract.py tests/contracts/design/test_sidebar_navigation_standard_contract.py
python scripts/verify_sidebar_navigation_standard.py
```

Developer Check must include Jinja macro rendering tests, source-access negative tests, scanner-state cases and both Findings pagination directions. Human UAT must still verify active/sidebar collapse/mobile, 6 canonical viewports, light/dark, visible deep links, current/partial/stale/empty scanner data and no misleading zero/all-clear. Passing static tests alone does not satisfy human acceptance.
