# Integrations Full Audit — 31 July 2026

## Audit Boundary

This review covers every active Integrations page and the provider-neutral integration kernel:

- Integrations Overview;
- Kubernetes Registry;
- Kubernetes Detail and Registry Details;
- Prometheus Registry and Coverage;
- Alertmanager Registry and Coverage;
- source-binding workspace;
- capability validation;
- runtime refresh and history;
- inventory/lifecycle context;
- provider adapters, resolver, compatibility, validation, runtime persistence, and route ownership.

No Integrations UI or runtime behavior is changed by this audit. Findings are recorded for review before implementation.

## Executive Assessment

| Area | Assessment | Notes |
|---|---|---|
| Provider architecture | Strong | Registry, adapters, capability contracts, runtime jobs, and provider ownership are clearly separated. |
| Operational workflow | Strong | Test Connection, Full Validation, Binding Validation, and Runtime Refresh have distinct responsibilities. |
| Kubernetes detail depth | Strong | Connection, capability, runtime, RBAC, lifecycle, inventory, and deletion boundaries are well covered. |
| Cross-provider visual consistency | Needs improvement | Provider pages and runtime views still rebuild labels, filters, tables, metrics, and pagination locally. |
| Responsive density | Needs improvement | Several workspaces retain arbitrary grid widths and micro typography from earlier revisions. |
| Runtime/history reuse | Partial | One large shared runtime-history component exists, but Kubernetes still uses a provider-local wrapper despite the documented direct-include contract. |
| Test coverage | Insufficient | Integration-specific automated coverage is concentrated on runtime recovery and Kubernetes history pagination. |
| Legacy/dead presentation | Confirmed | One unreferenced binding-validation partial remains; semantic badge presentation is duplicated from the global component. |

## What Is Already Correct

### Integrations Overview

- Catalog and Runtime are separate operator goals.
- Runtime posture is read from persisted observations and does not require live provider access to open the page.
- Provider, Health, and Readiness are distinct filters.
- Canonical detail routes are used for Kubernetes, Prometheus, and Alertmanager.

### Kubernetes Registry and Detail

- Registry defaults to five rows and retains 5/10/25/50 pagination.
- Connection identity, environment, compatibility profile, readiness, and action ownership are visible.
- Full Validation and Runtime Refresh are queued independently and duplicate work is guarded.
- Capability evidence, RBAC, stable API selection, legacy fallback, and lifecycle status are not collapsed into one health label.
- Inventory/lifecycle deletion explains removed, retained, and blocking records before destructive action.

### Prometheus and Alertmanager

- Reusable source instances are separated from Kubernetes scope bindings.
- Coverage and source inventory are separate operational views.
- Full Validation remains authoritative for compatibility and capabilities.
- Runtime Health remains lighter than Full Validation.
- Provider instances use canonical manage workspaces outside this registry module.

### Binding Workspace

- Source readiness, binding validation, and effective resolution are conceptually separate.
- Duplicate/conflicting binding creation is guarded in the service boundary.
- Operational feedback is persisted to Activity Audit and toast infrastructure.

## Confirmed Visual and Component Debt

### 1. Integration-specific semantic badge

```text
app/templates/integrations/partials/_status_badge.html
```

This component duplicates semantic mapping, icon selection, sizing, and classes already owned by `components/table_label.html`. It is referenced broadly, so migration should be deliberate and contract-tested, but it should not remain a second semantic system indefinitely.

### 2. Unused binding-validation partial

```text
app/templates/integrations/partials/_binding_validation_posture.html
```

No active template or test imports this macro. It is dead presentation code and should be removed after confirming no out-of-tree deployment override depends on it.

### 3. Runtime-history wrapper conflicts with documented contract

```text
app/templates/integrations/kubernetes/partials/_runtime_history.html
```

The file is only a six-line variable adapter around the shared runtime-history component. `INTEGRATION_MANAGE_WORKSPACE.md` currently prohibits provider-local wrappers. Either remove the wrapper and pass variables directly from the route, or revise the standard to explicitly allow a thin provider adapter. The current code and documentation disagree.

### 4. Repeated provider inventory geometry

Prometheus and Alertmanager maintain parallel versions of:

- inventory card;
- filter row;
- source table/list;
- pagination footer;
- coverage context;
- readiness labels.

The information is provider-specific, but the shell, filters, row geometry, actions, empty state, and pagination should be shared.

### 5. Runtime Overview uses page-local analytics patterns

The Runtime Overview currently owns local implementations for:

- summary metrics;
- filter select classes;
- table headers;
- loading bar;
- action buttons;
- two pagination footer branches.

Primary runtime metrics use `bg-surface-hover`, which conflicts with the current bright-evidence hierarchy used elsewhere in KAORI.

### 6. Arbitrary typography and layout debt

The audit found arbitrary text, tracking, width, or grid utilities across most Integrations pages, concentrated in:

- Integrations Overview;
- Kubernetes Capability Workspace;
- Kubernetes Connection Contract;
- shared Runtime History;
- Prometheus and Alertmanager inventory content.

These remain functional, but they should be migrated to shared typography and workspace macros during the next approved redesign.

## Confirmed Functional Concerns

### 1. Kubernetes runtime-history full-page fallback ignores requested page

`kubernetes_detail()` always calls `_kubernetes_detail_context(..., include_history=True)`, and that helper loads history with page `1` and per-page `5`.

The HTMX history endpoint respects `page` and `per_page`, but a normal link or browser fallback to:

```text
/integrations/kubernetes/<cluster_id>?page=2&per_page=10
```

returns the first history page. The route and fallback URL ownership should be aligned.

### 2. Numeric pagination behavior is inconsistent

Several registry/runtime panels use HTMX for Previous/Next but call `numeric_pages()` without an HTMX target. Numbered pages therefore perform full-page navigation while adjacent controls update only the owning panel.

This is not data corruption, but it creates inconsistent interaction, focus, and loading behavior.

### 3. Binding persistence unexpected-error path lacks exception logging

`_binding_response()` records sanitized operational feedback for unexpected exceptions but does not call `current_app.logger.exception(...)`. The Activity Audit record is useful for users, but maintainers need the original stack trace for diagnosis.

### 4. Sparse provider-workspace tests

The current repository has focused integration coverage for:

- runtime recovery;
- Kubernetes runtime-history pagination.

It does not sufficiently lock:

- all registry filters and pagination fallbacks;
- provider coverage pagination;
- Full Validation task status access;
- binding creation conflicts;
- provider-specific empty/degraded rendering;
- canonical runtime-history behavior across all three providers;
- route/template existence for every action.

### 5. Alertmanager README documentation drift

The Alertmanager module README lists `schemas.py` as a provider-owned file, but the active package has no such file. The ownership statement should point to the actual contracts/normalizers or the missing schema module should be restored if intentionally omitted.

### 6. Large orchestration modules

The following files are operationally dense and should be split by responsibility when behavior is next changed:

```text
app/integrations/validation/tasks.py      ~1000 lines
app/integrations/service.py                ~800 lines
app/integrations/routes.py                 ~500 lines
```

This is not a rewrite request. The concern is reviewability, test isolation, and accidental cross-provider regression.

## Page-by-Page Recommendation

| Page | Keep | Improve after approval |
|---|---|---|
| Integrations Overview | Catalog/Runtime separation, persisted posture, provider filters | Shared bright metric strip, shared filter bar, shared record pagination, consistent HTMX ownership |
| Kubernetes Registry | Current content and five-row density | Shared registry row/header/filter geometry; remove arbitrary micro typography |
| Kubernetes Detail | Four-domain information architecture and technical evidence depth | Normalize section headers/surfaces; reduce repeated guidance; resolve wrapper/document conflict |
| Prometheus Registry | Coverage-first workflow and reusable-source model | Share inventory/filter/pagination shell with Alertmanager |
| Alertmanager Registry | Coverage-first workflow and deployment-type filter | Share inventory/filter/pagination shell with Prometheus; correct README drift |
| Binding Workspace | Validation and resolution separation | Remove dead posture macro; standardize status/summary components |
| Runtime History | Technical depth, diagnostics, retention link, five-row default | Split large template into shared summary/row/detail components; normalize typography |

## Proposed Implementation Order

1. Fix full-page Kubernetes history pagination and add route tests.
2. Add a canonical Integrations semantic-status adapter backed by `table_label`.
3. Promote provider registry/filter/pagination shells shared by Prometheus and Alertmanager.
4. Standardize Integrations Overview Runtime on bright evidence and shared pagination.
5. Decompose shared Runtime History without changing its information contract.
6. Remove dead presentation files and reconcile documentation.
7. Split routes/service/validation tasks only alongside focused behavioral tests.

## Approval Boundary

The audit intentionally does not modify Integrations templates or backend behavior. Each implementation group should be reviewed against the screenshots and operational workflow before cutover, because these pages contain connection, validation, capability, and lifecycle actions with higher regression impact than read-only Analytics presentation.
