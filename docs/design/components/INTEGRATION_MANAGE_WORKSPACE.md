# Integration Manage Workspace

## Purpose

The Integration Manage Workspace is the shared KAORI structure for managing one registered provider connection. Alertmanager is the reference implementation. Prometheus must use the same information architecture, visual hierarchy, interaction model, and technical evidence depth while preserving metrics-specific terminology.

## Four-tab contract

A provider manage page uses these tabs when the provider supports the corresponding domains:

1. **Configuration** — edit the reusable connection contract inline.
2. **Validation & Capabilities** — inspect compatibility, required capabilities, technical evidence, dependent-domain readiness, and remediation.
3. **Runtime & History** — inspect current health, diagnostics, readiness boundary, and rolling observations.
4. **Scope & Resolution** — create governed bindings and inspect effective-source selection.

The tab bar, summary row, content shell, loading states, empty states, and pagination follow the same shared components across providers.

## Configuration contract

Configuration is edited inside the manage workspace. Do not require a second edit page or place an `Edit Configuration` action inside the tab.

The Configuration tab contains:

- three peer-level Violet Workspace Summary Cards;
- one inline form for identity, endpoint, access, compatibility, security, and operational controls;
- one primary Info Flow explaining how a saved change returns to governed use;
- optional Information Guide and Related Page Card in the right-side contextual column.

A legacy edit URL may redirect to `#configuration` for bookmark compatibility, but it must not render a separate edit workspace.

## Validation & Capabilities contract

Validation must expose more than a readiness label. The technical matrix provides, when applicable:

- capability name and category;
- Required or Optional classification;
- current evidence status;
- latest sanitized evidence;
- exact API, query, or discovery probe;
- success criteria;
- required provider/exporter/recording-rule configuration;
- operational impact;
- source owner;
- dependent KAORI modules;
- technical sub-checks;
- recommended remediation.

The capability catalog remains visible before the first validation and uses `Not Observed` state rather than disappearing.

Dependent operational-domain readiness is shown separately from provider capability evidence. Full Validation is the authoritative action that rebuilds this contract.

## Runtime & History contract

Runtime follows the shared Alertmanager structure:

- three Violet Workspace Summary Cards;
- Runtime Health & Diagnostics header with one `Refresh Runtime` action;
- current Health, Readiness, Response Evidence, and Capability Context cards;
- shared Health Interpretation;
- ordered Diagnostic Pipeline;
- Recent Runtime Observations with default five rows and `5 / 10 / 25 / 50` page sizes.

Runtime health and validation readiness are separate states. A source may be ready but currently unhealthy, or healthy but still awaiting Full Validation.

## Scope & Resolution contract

Scope management is performed inside the manage workspace, not through a separate registry-only workflow.

The workspace contains:

- existing scope bindings and removal actions;
- an inline Create Binding form;
- role and numeric priority;
- duplicate and conflicting-primary guardrails;
- consumer-specific effective-source resolution;
- candidate evidence, missing binding coverage, and missing technical capabilities;
- lifecycle deletion after every binding is removed.

Resolution detail must show why a candidate was selected, eligible, or skipped. Provider-specific consumers may require different technical capability sets while sharing the same canonical binding.

## Shared visual contract

- Provider Hero uses the shared KAORI Hero Context Panel.
- Tabs use the shared selected Violet state and technical badge.
- Peer summaries always use Workspace Summary Card.
- Main workflow uses Info Flow.
- Secondary ordered guidance uses Context Guidance Card.
- Non-sequential reference information uses Information Guide Card.
- Current runtime posture uses Health Interpretation.
- Persisted-object deletion uses the KAORI destructive confirmation modal.

## Provider-specific boundary

Shared structure does not mean identical copy. Provider-specific technical contracts remain explicit:

- Alertmanager: API availability, alerts, silences, status, routing-related evidence, and alert-source resolution.
- Prometheus: instant/range query APIs, metrics and labels, PromQL contracts, retention, Kubernetes analytics capabilities, and metrics-source resolution.

The provider remains authoritative for execution. KAORI provides validation, governance, historical evidence, and controlled source resolution.

## Prohibited patterns

- A separate edit page as the normal Configuration flow.
- An `Edit Configuration` button inside the manage tab.
- Capability detail reduced to a single status label.
- Hiding the capability catalog before first validation.
- Provider-local runtime score layouts when Health Interpretation exists.
- Runtime health presented as validation readiness.
- Scope bindings managed only from another page.
- Resolver results without decision reason or missing-capability evidence.
- Dynamic route construction in Jinja for lifecycle actions.

## Review checklist

- [ ] Configuration saves inline and returns to `#configuration`.
- [ ] Legacy edit URL redirects to the inline tab.
- [ ] Validation shows the complete technical capability catalog.
- [ ] Full Validation refreshes the matrix through the shared workspace.
- [ ] Runtime matches the shared Health Interpretation and history layout.
- [ ] Scope supports create, remove, resolution evidence, and governed deletion.
- [ ] Empty and not-observed states render without provider access.
- [ ] All actions have registered routes and server-side guardrails.
