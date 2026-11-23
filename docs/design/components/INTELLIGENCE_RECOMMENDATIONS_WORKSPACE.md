# Intelligence Recommendations Workspace

## Canonical Composition

The Recommendations hero remains the Intelligence posture reference. The workspace below it uses:

1. A KAORI section header with the loading bar placed below the title/status row.
2. Auto-refresh HTMX filters with no Apply button.
3. A responsive recommendation table on desktop and compact cards on smaller screens.
4. One `View Details` modal action per recommendation; expandable inline evidence is not permitted.
5. Canonical pagination: the left footer group owns `Showing a–b of n` and `Rows`; the right group owns Previous, numeric pages, and Next.

## Filter And Pagination Contract

Search uses a short debounce. Select controls refresh on change. Filter requests:

- reset the result page to 1;
- replace only `#recommendations-results-content`;
- preserve the filter controls and current scroll position;
- update the browser URL;
- display the shared KAORI loading bar;
- cancel stale in-flight result requests;
- preserve non-HTMX GET fallback behavior.

Numeric pagination, Previous, Next, and page-size changes also replace only `#recommendations-results-content`. Pagination must use `show:none` and `focus-scroll:false` so result changes do not jump the operator back to the beginning of the workspace.

Reset is the only operation that replaces the complete `#recommendations-workspace-content`, because the form controls must return to their default state.

## Record Summary Contract

The primary Recommendation column shows a concise operational summary. Examples, long technical identifiers, and supporting evidence remain in the detail modal. The service owns summary compaction so desktop and mobile records use the same wording.

**Concise row projections (#4833, November 2026 Visual UAT):** Table titles and
supporting sentences are limited to a compact presentation budget (64 characters
before existing word-boundary compaction), independent of the full recommendation
`title`, `summary`, `recommended_action`, immutable rule and source evidence.
For committed Kubernetes Tenant Allocation capacity findings with a verified
`capacity_state`, use semantic copy such as **Tenant allocation: Overcommitted**
instead of repeating a long namespace in Recommendation; shorten the associated
`@tenant:...:resource-quotas` scope to **Tenant resource quotas**. Never infer
capacity posture when the committed state is missing. Unrecognized long asset
scope strings use a bounded display projection, not changes to their source
identity. The complete original title/scope remain accessible through native
cell title attributes and the owning Review modal. Keep semantic source names,
evidence-kind labels, priority and AlertCase lifecycle unchanged, with no
deduplication or aggregation of underlying findings. Apply the same display
projection on desktop and mobile, and keep paginator/default 5 rows unchanged.


**Recommendation record visual alignment (#4833, operator UAT 2026-11-15):**
Retain the canonical shared `table_ui` row, cell and label primitives,
vertically centered cells, accessible caption/column headers, right-aligned
Review detail control and existing committed-source fields. The six-column
desktop table allocates 29% Recommendation, 22% Affected Scope, 17% Evidence,
15% Alert Handling, 8% Priority and 9% Details to accommodate tenant-level
technical scope identifiers and explanatory alert states. Within each cell,
use a balanced minimum-height content group, consistent primary/secondary
typography and compact badges; the information hierarchy, not colored blocks,
distinguishes the cells. Long recommendation titles, scope identifiers and
evidence titles use a two-line maximum with a native full-value title for
pointer users; source keys, scopes, evidence semantics and details remain
available through the existing Review modal. Keep the recommendation
supporting sentence one concise line on desktop and two lines in mobile cards.
Alert Handling retains its complete canonical state mapping and source-derived
status label; concise helper copy may wrap to two lines. Mobile scope values
may break only when needed to prevent overflow. Never invent display fields,
execute provider reads, change AlertCase lifecycle or duplicate a recommendation
engine to solve a presentation issue.

**Single Evidence type label and concise review heading (#4833,
follow-up UAT 2026-11-15):** In the desktop Evidence cell, display **exactly
one** shared `table_label.metadata_label` representing the source-backed
`logic_type_label` (Recommendation or Governance Check). Do not add an
additional provider chip, including Harbor, in the table. Keep the source title
as the primary field and retain an optional provider identity in the source
title tooltip and full Review modal evidence. This preserves consistent
one-label-per-record density without conflating the rule type with its provider.
Keep the canonical compact label component; do not introduce a new status family
or colored surface.

For high-Pod-restart recommendations only, the Recommendation Review modal
header uses a one-line-at-desktop summary derived from the existing committed
Kubernetes evidence (`evidence_window`, `affected_count`,
`total_restart_count`, `max_restart_count`). The full original source summary
remains on the native title and the detailed counts/asset identities remain
in the Case Brief, Affected Resources, and Evidence Ledger. If measured fields
are absent or inconsistent, retain the full source summary instead of
fabricating or inferring a zero. On narrower widths the headline can wrap
normally; avoid horizontal page overflow and do not truncate source fields
in the evidence/detail area. No live provider requests or AlertCase semantics
change.

## Detail Modal Contract

Recommendation evidence is rendered through the shared resource-detail modal system with an Intelligence context label. The modal uses:

- concise title and summary;
- a four-cell evidence summary strip;
- `Finding Overview` and `Evidence Contract` as peer cards;
- compact `Affected Context` evidence cells;
- one full-width `Recommended Action` section;
- evidence-boundary and validation callouts at the bottom.

The main KAORI scroll container reserves a stable scrollbar gutter. Opening or closing the modal must not resize the page or shift the underlying workspace.

## Compact Filter Layout

Recommendations use a two-row desktop filter layout. The first row owns Search, Domain, Provider Coverage, and Signal Source. The second row owns Severity, Category, Resource Type, and Rule Type. Search receives the largest width because it accepts free-form operational evidence terms. The shared Rule Catalog filter partial keeps its existing layout until the Rule Catalog is reviewed separately.

## Recommendation Summary

**Recommendation Summary is a standalone KAORI section between the Hero and Recommendation Workspace.** It is not nested inside the filter/table workspace. The section reports matching findings, source-qualified domain distribution, critical/warning counts, active-filter state, and the committed-evidence boundary. Counts cover the full filtered result set rather than only the current pagination page. The initial Kubernetes, Object Storage, and Artifact Registry domain metrics remain visible with accurate zero counts, while additional recognized domains appear only when authorized matching findings exist. Integration registration, connector connectivity, or a catalog-only rule never becomes an invented finding or healthy zero indicator.

The Recommendation Workspace continues to own filters, records, and pagination. Filter and pagination requests replace only `#recommendations-results-content`; the standalone Summary is refreshed with an HTMX out-of-band swap so it remains synchronized without rerendering the filter form or collapsing the workspace hierarchy. Reset may replace the complete workspace while refreshing the standalone Summary through the same OOB contract.

### Recommendations header, Guides, and filter actions (#4819)

The standalone **Recommendation Summary** header includes a shared **dynamic
Indicators** metadata label adjacent to its title. The baseline remains five
metrics (Matching Findings, Kubernetes, Object Storage, Artifact Registry,
Priority), with any additional source-qualified domain metrics inserted before
Priority. The number and responsive grid columns follow the rendered metric
count; existing shared posture metric and divider components are mandatory.
For example, an authorized committed Secrets & PKI finding may add a sixth
metric, but its provider must never be inferred as an independent domain. New
integrations such as Source Control/GitHub or Orchestration/Ansible do not add
a finding count until an approved central evaluator has produced committed,
permission-scoped evidence. Server/HCI are not assumed healthy just because
their domain appears in a selector. A plain shared section intro,
**Recommendation Review**, appears between the Summary and owning Workspace;
do not add another container or duplicate summary statistics.

**Recommendation Workspace** keeps its own title and description, with one
title-adjacent shared neutral metadata label, **Filtered Review**, followed by
exactly one accessible **Recommendations Guide**. The Guide explains
committed finding ownership, Alert Intelligence/Rule Catalog handoffs,
filter/pagination semantics, reset behavior and evidence qualification.
Reuse `table_label.metadata_label` and `info_tip.render(variant='guide')`;
do not display two adjacent Guide badges or implement a page-local popover.

The owning Workspace header groups source-derived status on the right and the
canonical `registry_ui.clear_filters_action` immediately before it when filters
are active. The legacy results strip (`Recommendations / N Results`) is removed
because Summary metrics and canonical pagination already communicate counts.
Clear Filters must retain its full-workspace reset target; filter/pagination
requests must not rerender the filter form. Result HTMX responses update the
right-side header action/status group out of band alongside the established
Hero and Summary OOB updates, preventing stale status or a stranded reset
button. Reset requests similarly refresh this header through their results
partial. Keep non-HTMX GET fallback, URL sync, default pagination 5,
light/dark responsive layout, keyboard focus and no infrastructure mutations.

Recommendations remain evidence-backed findings. The workspace may describe live-validation and remediation steps, but it must not expose a direct infrastructure execution control; live validation remains with the owning operational workspace and governed execution remains with Automation Control.


## Audit Remediation — Evaluator, Evidence and Scope (#1501–#1503)

The server must narrow evaluators to the selected canonical domain and an exact Rule Catalog key when opening a finding detail; missing alert-policy overrides must consume the already-batched policy map rather than cause per-finding SQL. Source/domain workers remain authoritative, and Central Intelligence owns finding semantics. All-domain GET still evaluates all applicable domains; UAT must benchmark this operation on large estates before claiming complete bounded performance.

The Recommendations Hero and **Recommendation Summary** are filter-scoped. Their presentation is synchronized by HTMX out-of-band replacements (`#recommendation-hero-posture` and `#recommendation-summary-section`) while results and pagination remain independently owned; no stale global Hero posture may remain after an AJAX filter change. Matching findings, severity, actionable counts, baseline Kubernetes / Object Storage / Artifact Registry distribution, and any additional eligible domain metrics are computed across the full matching set **before page slicing**, not from unrelated-domain findings. The projection consumes already server-authorized findings; `secrets_pki` remains gated by both Intelligence and Secrets & PKI view permissions and never publishes unauthorized underlying certificate identities. Filter source status is catalog-only and must not silently constrain Recommendations.

The Alert Handling selector includes Open, Source Unknown, Resolved · Verify, Resolved, Withdrawn, Retired and Accepted Risk states. The list/modal must retain AlertCase lifecycle provenance and must not offer a fresh manual promotion action when a historical or source-unknown case already exists.

**Evidence availability is not finding absence.** The Recommendations projection reports evaluator failures explicitly and classifies a conservative 24-hour committed inventory baseline, distinguishing `baseline_recent`, `partial`, `unavailable` and `not_collected`. `baseline_recent` does **not** certify complete metrics, scan or rule coverage. The empty state differentiates no matching filters, incomplete source evidence and no active findings, without asserting infrastructure health. A worker/reconciliation consumer must fail on evaluator SQL error rather than reconcile source alerts against fabricated no-findings output.

Current active recommendations are derived from committed current-state evidence. Historical Tenant Audit and policy/preflight events stay in immutable Audit evidence instead of being presented indefinitely as ongoing active conditions. Enabled/active provider eligibility and source freshness are prerequisites for current Object Storage findings. An active finding with Accepted Risk remains visible as evidence while escalation is suppressed by its governed Rule Exception.



## Catalog-to-Recommendations coverage audit (RC.6 operator review, 2026-11-23)

Source authority: `app/definitions/catalogs/intelligence/rules.yaml` (61 definitions), `app/intelligence/service.py::_build_recommendation_findings`, `app/intelligence/alert_intelligence/recommendation_source.py`, `app/intelligence/rule_presentation.py`, and the per-domain committed evidence builders. These are **repository capability declarations**, not a live provider inventory or verified runtime execution count.

| Canonical capability | Rule Catalog definitions | Central Recommendations evaluator | Evidence and limitation |
| --- | ---: | --- | --- |
| Kubernetes (including Tenant Governance) | 38: 36 Available, 2 Imported Signal | Yes, multiple committed inventory/governance/runtime/TLS evaluators | The two `alertmanager`-sourced enrichment definitions are **Imported Signal**, not automatically active findings; provider alert state remains owned by Alertmanager/Alert Intelligence |
| Object Storage (MinIO provider coverage) | 12 Available | Yes | Current enabled provider identity, committed fresh inventory/analytics; provider filters do not create parallel `minio.*` rules |
| Artifact Registry (Harbor provider coverage) | 6 Available | Yes | Committed Registry inventory/security/runtime evidence; **Runtime Correlation** is a separate source qualification before interpreting absent cross-domain exposure |
| Secrets & PKI (Vault provider coverage) | 1 Available | Yes, authorization-gated | Committed PKI certificate population; requires both `intelligence.view` and `secrets_pki.view`. Visibility of one rule in Catalog does not demonstrate a current matching certificate finding |
| Server | 2 Reserved Plan | No admitted central evaluator | Catalog only; no verified current operational recommendations |
| HCI | 2 Reserved Plan | No admitted central evaluator | Catalog only; no verified current operational recommendations |
| Source Control / GitHub | No canonical central recommendation definitions | No | Integration and committed repository inventory remain authoritative in Source Control. A new security/governance evaluator requires a separate approved, evidence-backed workstream |
| Orchestration / Ansible | No canonical central recommendation definitions | No | Ansible execution authority remains external; KAORI orchestration/audit does not imply a recommendation evaluator |
| Alertmanager / imported alerts | 2 Kubernetes `Imported Signal` definitions, no independent alert domain | Not a direct recommendation projection | Alert Intelligence owns alert/case/source lifecycle; committed recommendation findings may be promoted into AlertCases only under approved policies. Do not copy firing provider alerts into canonical findings without a matching committed-evidence rule |
| Metrics Source | No direct `metrics_source_metrics`-sourced definition in current Catalog | Not an independent domain evaluator | Analytics may consume qualified committed metrics and alerts; metrics registration alone must not produce an Intelligence finding |

**Source-readiness correction:** `runtime_correlation_evidence_readiness` distinguishes `not_materialized`, `inputs_changed`, `refreshing`, `refresh_failed`, `stale`, and `ready`. For the unready states, Recommendations shows the source-qualified **Runtime Correlation Required** operational callout (with an owning Runtime Usage CTA) and records `evidence_readiness.source_gaps` independently of `evaluation_issues`. Missing correlation alone returns an incomplete/partial evidence posture when otherwise recent committed inventory exists; it never claims that an evaluator failed. A real SQL evaluator/read failure still remains `unavailable` with no findings (or `partial` if authorized findings survive). If all required inventory is absent, `not_collected` remains authoritative. This correction changes **UI interpretation**, not the AlertCase reconciler's separate fail-closed missing-correlation check.

**Decision boundary:** This audit does **not** authorize new Server/HCI, Source Control, Ansible, imported-alert, or direct Metrics Source evaluators. Each requires a child issue with a committed source contract, domain-specific rule authority, least-privilege scope, source freshness, testable positive/negative evidence and independent governance review. Never infer integration health or a recommendation count from registered connectors or Catalog `Available` labels alone.
