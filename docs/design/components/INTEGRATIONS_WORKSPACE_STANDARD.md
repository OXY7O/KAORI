# Integrations Workspace Standard

> Status: canonical and implemented.

## Purpose

This standard aligns the Integrations Overview, provider registries, source bindings, runtime evidence, and Kubernetes connection workspace without flattening provider-specific operational detail.

## Global Hierarchy

```text
Hero
Controls / Filters
Bright Operational Evidence
Provider-Specific Technical Evidence
Darker Interpretation or Recommended Action
Pagination / Lifecycle Actions
```

Primary source, runtime, validation, capability, binding, and coverage evidence uses `bg-surface-card`. `bg-surface-hover` is reserved for interpretation, warning context, remediation, attention strips, and destructive-boundary guidance.

## Shared Components

Canonical Integrations presentation lives under:

```text
app/templates/integrations/components/_workspace.html
app/templates/integrations/components/_provider_registry.html
app/templates/integrations/components/_semantic_status.html
```

Responsibilities:

- `_workspace.html` owns section shells, headers, bright metric strips, controls, and interpretation panels.
- `_provider_registry.html` owns provider-registry headers, filters, loading, and full-page/HTMX pagination ownership.
- `_semantic_status.html` is the Integrations adapter to global `components/table_label.html`; it must not define an independent palette.

Provider templates supply factual labels, icons, endpoint data, compatibility evidence, and actions. They do not copy shared geometry or semantic colors.

## Provider Registry Contract

Prometheus and Alertmanager registries share:

- one registry shell;
- Search plus provider-specific filters;
- five-row default and `5 / 10 / 25 / 50` page sizes;
- `Showing a–b of n` footer;
- explicit full-page `href` and owning-panel HTMX URL;
- one consistent identity and action geometry;
- readiness, compatibility, binding count, and factual provider fields;
- one empty state.

Provider-specific evidence remains explicit. Prometheus retains profile/query evidence. Alertmanager retains deployment type and notification-specific evidence.

## Coverage Contract

Provider coverage uses the shared coverage component and the same pagination ownership as provider registries. Normal links always resolve the complete provider page; HTMX requests replace only the coverage panel.

Coverage status is not provider runtime health. `Covered`, `Uncovered`, missing binding, validation-required binding, and incompatible source remain distinct states.

## Runtime Overview Contract

Runtime Overview separates:

```text
Bright Summary Metrics
Provider / Health / Readiness Filters
Bright Runtime Records
Shared Pagination
```

Health, Validation Readiness, and Capability Attention are separate signals. A healthy runtime observation does not imply Full Validation readiness.

## Semantic Status Contract

Global semantic rendering is owned by:

```text
app/templates/components/table_label.html
```

Integrations uses `integration_status(...)` only as an adapter for provider-specific labels and icons. Canonical states include:

```text
Ready
Validation Required
Compatible
Compatible With Warnings
Unsupported Version
Capability Mismatch
Not Observed
Legacy Fallback
Uncovered
```

Backend services emit semantic state keys and factual labels. They must not emit Tailwind classes as a presentation API.

## Compact Label Role Contract

Integrations follows the global label decision from `components/table_label.html`. The least visually heavy representation that preserves meaning is required.

```text
Operational state in a sparse card/header? → status_label (text only)
Operational state repeated in a table/list? → status_indicator_label (semantic dot)
Context, scope, provider type, category, or count? → metadata_label
Exceptional security/eligibility/high-attention state? → special_label
Ordinary value, timestamp, version, name, or count in a sentence? → plain text
```

Icon rules:

- Lucide icons are permitted in metadata labels only when the icon adds independent context, such as scope, provider, source, time window, or externally linked identity.
- Counts, lifecycle words, readiness states, provider names beside an existing provider icon, and repeated table statuses do not receive Lucide icons.
- A semantic dot from `status_indicator_label(...)` is a scan aid, not a decorative icon.
- `integration_status(...)` must choose `display='text'` or `display='indicator'` on newly touched overview/table surfaces. `display='icon'` is retained only for an audited provider-specific exception.
- Icon + border compact labels are reserved for `display='special'` and must represent an exceptional posture, security boundary, or eligibility gate.

Integration Overview is the reference implementation: scope metadata may carry a filter icon, count metadata remains iconless, provider lifecycle/readiness uses text or dot labels, and runtime table states use dot labels.

## Technical Evidence Contract

Capability and validation evidence follows a stable order:

1. capability identity and requirement level;
2. semantic result;
3. observed evidence;
4. success criteria;
5. operational impact;
6. source owner;
7. remediation;
8. optional runnable technical check.

Runnable commands or expressions use technical-value presentation. Explanatory prose remains normal KAORI typography. Technical matrices may use horizontal scrolling only where preserving side-by-side column comparison is operationally necessary.

## Runtime History Contract

One shared runtime-history component owns:

- summary metrics;
- immutable observation records;
- health, readiness, compatibility, diagnostics, and drift evidence;
- five-row default;
- `5 / 10 / 25 / 50` page size;
- full-page and HTMX pagination ownership;
- a lifecycle-management action when permitted.

Provider routes pass the required context directly to:

```text
app/templates/integrations/partials/_runtime_history.html
```

Provider-local presentation wrappers are prohibited.

Full-page pagination must preserve route path arguments and open the owning workspace tab. HTMX pagination must call the partial endpoint and replace only the runtime-history region.

## Binding Contract

Source Readiness, Binding Validation, and Effective Resolution are separate evidence boundaries. A binding must not appear operational merely because the reusable source is Ready.

Long selectors, source identities, and scope keys use controlled wrapping. Unexpected persistence failures must record sanitized user-facing Activity Audit evidence and preserve the original stack trace with application exception logging.

## Action Contract

- Test Connection is synchronous and verifies submitted draft settings.
- Full Validation is asynchronous and authoritative for capability/readiness evidence.
- Runtime Refresh is asynchronous and lightweight.
- Binding Validation is asynchronous and scope-specific.
- Save, remove, and delete operations repeat guardrails in the service boundary.
- Every outcome records durable Activity Audit evidence and persistent feedback.

## Responsive Contract

- Avoid horizontal scrolling for registries when responsive records preserve all evidence.
- Technical matrices may scroll only when column comparison is essential.
- Long endpoints, selectors, capability names, and profiles use controlled wrapping and title/detail disclosure.
- Arbitrary micro typography, raw palette utilities, and page-local semantic badges are prohibited.
- Primary metrics remain bright even when their semantic state is Warning or Critical; severity is carried by labels and operational copy.

## Deliberate Technical-Matrix Exceptions

The following layouts may retain minimum widths because simultaneous comparison is the core task:

- Prometheus registry compatibility/runtime/binding matrix;
- Kubernetes capability and minimum-RBAC evidence matrices;
- dense validation evidence tables.

These exceptions must remain inside an owning `overflow-x-auto` region and must not force the entire page to scroll.

## Review Checklist

- [ ] Primary evidence is bright.
- [ ] Interpretation/remediation is darker.
- [ ] Health, readiness, compatibility, capability, and coverage remain separate.
- [ ] Semantic labels resolve through the global table-label component.
- [ ] Pagination preserves route arguments, active tabs, filters, and HTMX ownership.
- [ ] Normal navigation never opens a partial-only template.
- [ ] Every mutation has route, permission, service guardrail, Activity Audit, feedback, and exception-logging coverage.
- [ ] Provider-specific evidence remains factual after reuse.
- [ ] Empty, disconnected, not-observed, and validation-required states render without live provider access.
