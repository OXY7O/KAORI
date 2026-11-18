# KAORI Platform Operations — Data Lifecycle Final Lock v1

Status: Final Lock
Date: 2026-08-08
Owner: Platform Operations

## Scope

Data Lifecycle is the canonical cross-domain operational control plane for retention intent, verified archive storage, archive evidence, and safe cleanup. This lock moves ownership out of Settings without duplicating the archive-first engine or the canonical job runtime.

## Information Architecture

```text
Platform Operations
├── Jobs & Executions
├── Data Lifecycle
│   ├── Retention Policies
│   ├── Archive Storage
│   └── Archive History
└── Kubernetes Administration
```

`Data Lifecycle` appears immediately after `Jobs & Executions`. Settings does not expose Data Lifecycle as a submenu.

## Code Ownership

- `app/platform_operations/data_lifecycle/` owns routes, operator mutation orchestration, feedback, and workspace presentation.
- `app/templates/platform_operations/data_lifecycle/` owns the UI.
- `app/platform_operations/data_lifecycle/retention/` remains the domain-neutral lifecycle engine, adapters, archive writer, verification, cleanup safety, lock, task, and policy persistence layer.
- `app/platform_operations/jobs/` remains the canonical worker execution ledger. Data Lifecycle may enqueue canonical jobs only through the shared dispatcher.
- `app/settings/data_lifecycle_compat.py` is redirect-only compatibility. It must not render templates, mutate lifecycle data, or import retention execution services.

## URL Contract

Canonical URL:

`/platform-operations/data-lifecycle/`

Legacy `/settings/data-lifecycle/` endpoints remain temporary compatibility redirects. GET uses a normal redirect; mutation endpoints use method-preserving redirects so stale pages/bookmarks do not silently execute a second implementation.

## RBAC Contract

Canonical permissions are:

- `platform_operations.view_data_lifecycle`
- `platform_operations.manage_data_lifecycle`
- `platform_operations.export_data_lifecycle`

The ownership migration renames the former `settings.*_data_lifecycle` permission rows **in place** and changes their module to `operations`. Existing role-permission assignments therefore keep their permission IDs and access semantics. The migration also handles a defensive dual-row state without losing custom-role assignments.

## Workspace Contract

1. The page uses the shared KAORI Page Hero and Framed Workspace Tabs.
2. It does not own page-local tab geometry or hardcoded light-only tab surfaces.
3. Only registered archive adapters appear as managed domains. Roadmap/Planned Domain placeholders are not shown.
4. Retention Policies owns policy intent, exact preview, schedule intent, and manual archive requests.
5. Archive Storage owns shared archive-target posture and the archive-first safety boundary.
6. Archive History owns archive artifact, checksum, verification, cleanup, and download evidence. It is not a duplicate JobExecution registry.
7. Runtime state, retries, cancellation, worker readiness, and generic JobExecution details remain in Jobs & Executions.
8. Archive History pagination follows KAORI table standards with Title Case resource naming, visible `Rows`, and default 5 rows.
9. Dark mode is semantic-surface based. No `bg-white`, raw palette utility, raw hex, or page-local inline styling is accepted.

## Compact Policy Guidance and Source-Owned Coverage

The Retention Policies selected-domain header uses the canonical
`components/info_tip.html` title-level Guide (`variant='guide'`) where
source-specific policy details would otherwise make the workspace dense.
Every registered Retention Policy has a distinct, permission-safe title Guide
using the shared Info Tip pattern. Guides expand detailed source and safety
semantics while the visible policy summary and exclusions remain truthful.

- **Analytics Snapshots:** compact coverage cards identify materializations
  and reusable forecasts; the Guide retains capacity, utilization, storage,
  workloads, top-consumer and alert scope and the stale-serve/hot-retention
  cleanup safety boundary.
- **Generated Reports:** compact cards describe terminal report retention and
  verified report artifacts; the Guide retains Ready/Failed/Archived policy
  distinctions and explicit protection for Requested/Queued/Generating,
  active regeneration, and missing-safe-artifact cases. The Excluded footer
  targets two readable desktop lines, explicitly describing protected reports
  without altering the archive/cleanup eligibility contract. The Hot Source
  detail uses the concise `Reports metadata + PDF/XLSX/CSV` label for a
  single desktop row. Full artifact and safety context remains in the Guide,
  Lifecycle Coverage and storage ownership boundaries.
- **Administrative Audit Events:** a compact Excluded statement preserves
  non-admission of raw metadata, actor reconstruction, downloads, scheduling,
  cleanup, and record-level lookup. The existing Guide remains the full
  operator explanation; actual archive execution remains manual and
  non-destructive.

- **Job Executions:** archive committed terminal execution metadata and result
  references; the referenced domain-owned result datasets are not deleted by
  Job Executions retention.
- **Notification Delivery:** provider-neutral Manual Archive Only. Hot records
  retain deduplication, retries and channel dependencies; automatic scheduling
  and cleanup are disabled and queued/failed/retry-eligible records remain
  protected. The Coverage footer targets two readable desktop lines: manual
  archive-only ownership, blocked scheduling/cleanup, and a separate sentence
  making eligible manual archive requests explicit; eligibility, permission
  and actual execution remain governed by the domain.
- **Activity Audit:** one persisted notifications table serves both the
  account-scoped Notification Center and permissioned Activity Audit; transient
  toasts are neither persisted nor lifecycle-managed. Authentication audit
  remains a distinct audit stream within the approved coverage. Its coverage
  card uses the compact description `Authentication events follow the audit
  stream's lifecycle.` to target two readable desktop lines without implying
  that authentication events are stored in the notifications table.
- **Runtime Observations:** committed normalized Kubernetes, Object Storage,
  Metrics Source and Alertmanager observations are provider-neutral evidence,
  not a copy of provider configuration, credentials or live source authority.
- **Tenant Audit Evidence:** committed normalized Tenant correlations and
  identity/outcome references are governed while Kubernetes remains
  authoritative for raw audit logs and provider request/response bodies.
- **Automatic Run:** show compact policy/schedule prerequisite text and the
  genuine `lifecycle.next_schedule_label` as separate read-only lines.
  This date/time remains source-backed, including the configured timezone;
  no fallback may imply an executed or queued job.

Natural responsive wrapping is permitted; avoid forcibly clipped
`whitespace-nowrap`, static dates or hiding security-critical exclusions.
Copy updates do not alter archive-first safety, RBAC, underlying eligibility,
scheduled dispatcher interval, provider authority, or audit/evidence semantics.

The **Generated Report Evidence Protection** notice uses a compact one-line
desktop summary retaining SHA-256 verified archives before cleanup and protection
for pending/regenerating work; fuller status conditions remain in its Guide.
The **Notification Delivery** Coverage summary now targets **two lines** on the
reference desktop card; its two sentences remain source-owned and are not forcibly
clamped or broken by a page-local HTML variant. **Activity Audit** Coverage and
Excluded summaries also target two lines. Normal responsive wrapping is allowed
and must be visually checked.
For Generated Reports, the Excluded footer is intentionally **two lines**
at normal desktop widths, while its Hot Source detail targets **one line**;
do not apply forced no-wrap, ellipsis, or page-local layout changes to
security-sensitive exclusions. Viewport-specific browser evidence is required
to verify the final line count.

The mandatory Data Lifecycle Final Lock verifier must enforce the current
`Policy + schedule required.` message **and** the source-derived
`lifecycle.next_schedule_label` binding. Historical literal-copy checks must
not disable the actual schedule safety contract.

## Safety Invariants

- Cleanup never starts before the archive data and manifest checksums are verified.
- Selection remains frozen by immutable retention boundary and source IDs.
- Manual lifecycle execution uses `enqueue_canonical_job`; no direct Celery dispatch is owned by the page.
- Operational feedback and Activity Audit evidence are persisted for policy changes, execution requests, archive verification, and failures.
- Verified archive download remains separately permission-gated.
- Adding a future domain requires a registered retention adapter and explicit safety boundary before it can appear in the UI.

## Final Lock Enforcement

```bash
python scripts/verify_data_lifecycle_final_lock.py
python scripts/verify_platform_operations_final_lock.py
pytest -q tests/contracts/platform_operations/test_data_lifecycle_final_lock_contract.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
python scripts/verify_migration_graph.py
```
