# Integrations Workspace Standard

> Status: audited draft. Existing pages are not automatically migrated by this document.

## Purpose

This standard aligns the Integrations Overview, provider registries, bindings, runtime evidence, and Kubernetes connection workspace without flattening provider-specific operational detail.

## Global Hierarchy

```text
Hero
Controls / Filters
Bright Operational Evidence
Provider-Specific Technical Evidence
Darker Interpretation or Recommended Action
Pagination / Lifecycle Actions
```

Primary source, runtime, validation, capability, binding, and coverage evidence remains bright. Darker soft surfaces are reserved for interpretation, warning context, remediation, and destructive-boundary guidance.

## Provider Registry Contract

Prometheus and Alertmanager registries share:

- one registry shell;
- Search plus provider-specific filters;
- five-row default and 5/10/25/50 page sizes;
- `Showing a–b of n` footer;
- explicit full-page `href` and owning-panel HTMX URL;
- one consistent row identity block;
- readiness, compatibility, binding count, and action columns;
- one empty state.

Provider-specific fields remain explicit. Shared geometry must not erase Prometheus compatibility/profile evidence or Alertmanager deployment-type evidence.

## Runtime Overview Contract

Runtime Overview separates:

```text
Bright Summary Metrics
Provider / Health / Readiness Filters
Bright Runtime Records
Shared Pagination
```

Health, Validation Readiness, and Capability Attention are separate signals. A healthy runtime does not imply Full Validation readiness.

## Semantic Status Contract

Integrations should migrate toward `components/table_label.html` as the single semantic rendering owner. Provider services emit semantic keys and factual labels; templates do not emit a second independent palette.

The migration must preserve provider-specific states such as:

```text
Validation Required
Compatible With Warnings
Capability Mismatch
Not Observed
Legacy Fallback
```

## Technical Evidence Contract

Capability and validation evidence may be dense, but it must follow a stable order:

1. capability identity and requirement level;
2. semantic result;
3. observed evidence;
4. success criteria;
5. operational impact;
6. source owner;
7. remediation;
8. optional runnable technical check.

Runnable commands or expressions use technical-value presentation. Explanatory prose remains normal KAORI typography.

## Runtime History Contract

One shared runtime-history component owns:

- summary metrics;
- observation records;
- diagnostic evidence;
- lifecycle/capability drift;
- five-row default;
- 5/10/25/50 page size;
- full-page and HTMX pagination ownership.

Provider-local wrappers are allowed only when they contain variable assignment and no presentation. The preferred implementation is direct route context plus direct shared include.

## Binding Contract

Source Readiness, Binding Validation, and Effective Resolution are separate evidence boundaries. A binding must not appear operational merely because the source itself is Ready.

## Action Contract

- Test Connection is synchronous and tests submitted draft settings.
- Full Validation is asynchronous and authoritative for capability/readiness evidence.
- Runtime Refresh is asynchronous and lightweight.
- Binding Validation is asynchronous and scope-specific.
- Save, remove, and delete operations repeat guardrails in the service boundary.
- Every outcome records durable Activity Audit evidence and persistent toast feedback.

## Responsive Contract

- Avoid horizontal scroll for registries when a responsive record collection can preserve the information.
- Technical matrices may scroll only when column comparison is essential.
- Long endpoints, selectors, capability names, and compatibility profiles use controlled wrapping and title/detail disclosure.
- Arbitrary micro typography and page-local grid widths are not added.

## Review Checklist

- [ ] Primary evidence is bright.
- [ ] Interpretation/remediation is darker.
- [ ] Health, readiness, compatibility, and capability remain separate.
- [ ] All pagination controls preserve route arguments, filters, and HTMX ownership.
- [ ] Normal navigation never opens a partial-only template.
- [ ] Every action has route, permission, service guardrail, Activity Audit, and feedback coverage.
- [ ] Provider-specific evidence remains factual after reuse.
- [ ] Empty, disconnected, not-observed, and validation-required states render without live provider access.
