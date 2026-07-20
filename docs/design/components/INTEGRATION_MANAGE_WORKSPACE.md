# Integration Manage Workspace

## Purpose

The Integration Manage Workspace is the shared KAORI structure for managing one registered provider connection. Alertmanager is the reference implementation. Prometheus must use the same information architecture, visual hierarchy, interaction model, and technical evidence depth while preserving metrics-specific terminology.

## Provider registration contract

Before a reusable provider connection enters the manage workspace, the registration page follows one shared Prometheus and Alertmanager contract:

1. Define the canonical connection identity and connection contract.
2. Run a successful Test Connection against the submitted endpoint and access settings.
3. Issue a short-lived signed proof bound to the current user and exact submitted values.
4. Enable the Register action only while that proof remains valid.
5. Any connection field change must invalidate the proof immediately.
6. Repeat the network probe on the server immediately before persistence.
7. Record every test, rejection, failure, and successful registration as one toast and one durable Activity Audit record.

Test Connection proves reachability and the provider-specific basic compatibility boundary. It does not replace Full Validation, capability evidence, readiness assessment, or scope binding validation.

The registration contextual column uses this order:

- provider Registration Flow;
- Related Analytics or Intelligence Workspace;
- provider-specific compatibility or connection-type guidance;
- Connection Identity & Contract;
- After Registration guidance.

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

Provider capability probes are evidence expressions, not necessarily executable shell commands. Prometheus and Alertmanager render the probe label as normal KAORI content and place the expression value on a Violet soft surface without a copy action. Kubernetes RBAC probes may retain the terminal/copy treatment only when the displayed value is a complete CLI command that can be executed directly.

Dependent operational-domain readiness is shown separately from provider capability evidence. Full Validation is the authoritative action that rebuilds this contract. It must enqueue a dedicated Celery validation job, return the workspace immediately, display the standard loading bar under the block header, disable duplicate actions, and poll the task-specific partial through HTMX until completion.

## Runtime & History contract

Runtime follows the shared Alertmanager structure:

- three Violet Workspace Summary Cards;
- Runtime Health & Diagnostics header with one `Refresh Runtime` action;
- current Health, Readiness, Response Evidence, and Capability Context cards;
- shared Health Interpretation;
- ordered Diagnostic Pipeline;
- Recent Runtime Observations with default five rows and `5 / 10 / 25 / 50` page sizes.

Runtime health and validation readiness are separate states. A source may be ready but currently unhealthy, or healthy but still awaiting Full Validation. Runtime Refresh is a lightweight worker job and must preserve the latest full capability evidence; scheduled runtime monitoring must not rerun heavy capability discovery.

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
- [ ] Test Connection remains synchronous and lightweight.
- [ ] Full Validation, Runtime Refresh, and binding validation execute on the dedicated validation worker.
- [ ] Queue, completion, and failure outcomes produce Activity Audit records and persistent toast feedback.

## Kubernetes provider parity

Kubernetes uses the same manage-workspace hierarchy as Alertmanager and Prometheus, with provider-specific lifecycle terminology:

1. **Configuration** — canonical cluster identity, API endpoint, transport trust, access boundary, and authority contract.
2. **Validation & Capabilities** — served API discovery, effective RBAC, stable API selection, legacy fallbacks, blocked features, CLI verification, and remediation.
3. **Runtime & History** — worker-driven runtime refresh, diagnostics, and the shared Recent Runtime Observations component.
4. **Inventory & Lifecycle** — normalized KAORI consumers, shared observability-source bindings, retention boundary, and governed deletion.

The Kubernetes Add flow requires a successful synchronous Test Connection before Save Connection is enabled. KAORI issues a short-lived signed proof bound to the current user, identity fields, TLS policy, and kubeconfig fingerprint. Any form change invalidates the proof. The server verifies the proof and repeats the connection probe immediately before persistence. Test, rejection, persistence, and failure outcomes must create persistent toast feedback and Activity Audit records.

## Shared terminal evidence

Technical probes that can be executed from a shell are rendered with the shared terminal component rather than a neutral text box. The terminal contract includes:

- dark technical surface and monospace command text;
- a visible prompt marker;
- a concise label identifying the probe context;
- an accessible Copy action;
- sanitized commands only—never secrets, bearer tokens, passwords, or raw kubeconfig material.

Use this presentation for PromQL probes, Alertmanager API checks, `kubectl auth can-i`, and similar operator-verification commands.

## Shared runtime-history component

Prometheus, Alertmanager, and Kubernetes use one Recent Runtime Observations component. Provider wrappers supply only the provider label, route, loading ID, and runtime-history context. The shared component owns:

- title box and retention label;
- summary metrics;
- technical observation table;
- empty state;
- default five rows and `5 / 10 / 25 / 50` page sizes;
- enabled Previous/Next controls with active styling;
- disabled Previous/Next controls as non-interactive elements with `aria-disabled="true"`.

## Edit Connection Verification

Provider manage workspaces retain a lightweight **Test Connection** action inside the Endpoint & Access header. The action tests the submitted draft settings without mutating the saved connection. When an edit form leaves a password or bearer token blank and keeps the same authentication type, KAORI may reuse the encrypted/stored secret for the probe only. A newly supplied secret overrides it. Test outcomes are toast-only operational feedback and are always recorded in Activity Audit.

Edit verification does not gate Save by default. Saving a changed connection returns readiness to Validation Required, and Full Validation remains authoritative for compatibility, capabilities, RBAC evidence, and downstream readiness.

## Readiness Evidence Boundary

A provider can expose green capability rows while overall readiness remains Degraded because lifecycle, compatibility, authorization, retention, or runtime-health factors are evaluated separately. Every non-ready workspace must show the contributing factor, factor score, and remediation. Runtime history must retain the validation message so an operator can explain an historical score without reconstructing the original validation run.

For Kubernetes specifically, a legacy Kubernetes release can keep stable API capability rows Ready while lowering the weighted compatibility/lifecycle factor. The workspace must state this explicitly rather than implying that a hidden capability failed.

## Filesystem Analytics Contract

The Prometheus Storage Filesystem Contract requires a complete capacity-and-availability pair for either `/var` or `/`:

- `node_filesystem_size_bytes`
- `node_filesystem_avail_bytes`
- a canonical node identity label (`node`, `nodename`, or `kubernetes_node`)

A size series alone proves filesystem capacity collection but cannot calculate utilization or remaining headroom. Validation evidence must display all four registered queries, identify the missing half of each pair, and avoid generic exporter remediation when the metric exists but only part of the contract is observable.
