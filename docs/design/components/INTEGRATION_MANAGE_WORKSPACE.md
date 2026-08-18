# Integration Manage Workspace

## Purpose

The Integration Manage Workspace is the shared KAORI structure for managing one registered provider connection. Alertmanager is the reference implementation. Metrics Source must use the same information architecture, visual hierarchy, interaction model, and technical evidence depth while preserving metrics-specific terminology.

## Provider registration contract

Before a reusable provider connection enters the manage workspace, the registration page follows one shared Metrics Source and Alertmanager contract:

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

Retired edit URLs are not registered. The canonical detail route owns inline configuration and returns to `#configuration` after a successful save.

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

Provider capability probes are evidence expressions, not necessarily executable shell commands. Metrics Source and Alertmanager render the probe label as normal KAORI content and place the expression value on a Violet soft surface without a copy action. Kubernetes RBAC probes may retain the terminal/copy treatment only when the displayed value is a complete CLI command that can be executed directly.

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
- Metrics Source: provider-neutral registration, runtime, and binding ownership; adapter/query-specific transport evidence stays behind the selected backend adapter, while Kubernetes, Object Storage, and future consumer contracts remain binding-scoped.

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
- [ ] Retired edit URLs are not registered.
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

Kubernetes uses the same manage-workspace hierarchy as Alertmanager and Metrics Source, with provider-specific lifecycle terminology:

1. **Configuration** — canonical cluster identity, API endpoint, transport trust, access boundary, and authority contract.
2. **Validation & Capabilities** — served API discovery, effective RBAC, stable API selection, legacy fallbacks, blocked features, CLI verification, and remediation.
3. **Runtime & History** — worker-driven runtime refresh, diagnostics, and the shared Recent Runtime Observations component.
4. **Inventory & Lifecycle** — normalized KAORI consumers, shared observability-source bindings, retention boundary, and governed deletion.

The Kubernetes Add flow requires a successful synchronous Test Connection before Save Connection is enabled. KAORI issues a short-lived signed proof bound to the current user, identity fields, TLS policy, and kubeconfig fingerprint. Any form change invalidates the proof. The server verifies the proof and repeats the connection probe immediately before persistence. Test, rejection, persistence, and failure outcomes must create persistent toast feedback and Activity Audit records.

## Setup reference and validation ownership

Configuration setup references use one placement contract across providers: after the Operational Flow/Operational Context inside the Configuration body and before the workspace footer. The Kubernetes RBAC example is the visual reference; Metrics Source and future provider setup references must use the same hierarchy rather than appending a detached card after the shared configuration contract.

Validation ownership remains split by evidence boundary:

- **Provider/Core Validation** owns transport, provider compatibility, generic API/query capabilities, and provider readiness.
- **Binding Validation** owns asset-scoped consumer identity, required metric/label contracts, pairing rules, and consumer capability evidence.
- **General Validation** is the operator roll-up surface. It displays provider-core rows plus the latest completed binding-owned consumer rows; it does not create a second consumer validation engine.
- **Scope & Consumers** shows binding profile, selector, and validation state plus the action to validate that binding. Detailed missing evidence stays in General Validation `View More`.
- A binding without completed validation is `Validation Required`; provider readiness must not upgrade it to Ready or reinterpret it as Missing.

## Capability evidence and runnable checks

Capability Technical Detail separates explanation from executable evidence:

- **Why KAORI Checks This** uses normal KAORI body typography and explains the operational reason for the capability check.
- **Technical Checks** is expandable and contains the complete PromQL expression, Alertmanager API request target, or another provider-specific check.
- Runnable expressions use a Violet technical surface, monospace only for the expression itself, and an accessible Copy action.
- Shell-style terminal presentation is reserved for actual CLI commands such as `kubectl auth can-i`; PromQL and API request targets must not be presented with a fake shell prompt.
- Technical evidence must never contain passwords, bearer tokens, kubeconfig data, or other secrets.

## Shared runtime-history component

Metrics Source, Alertmanager, and Kubernetes include one Recent Runtime Observations component directly. Each owning workspace supplies the provider label, route, loading ID, and runtime-history context; provider-local wrapper templates are prohibited. The shared component owns:

- title box and a `Manage Lifecycle` button when the user can view Data Lifecycle;
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

The Metrics Source Storage Filesystem Contract requires a complete capacity-and-availability pair for either `/var` or `/`:

- `node_filesystem_size_bytes`
- `node_filesystem_avail_bytes`
- the canonical Kubernetes node identity label `node` (`node=<Kubernetes Node.name>`)

A size series alone proves filesystem capacity collection but cannot calculate utilization or remaining headroom. Validation evidence must display all four registered queries, identify the missing half of each pair, and avoid generic exporter remediation when the metric exists but only part of the contract is observable.

## Governed Integration Deletion

Provider deletion is a dependency-aware lifecycle operation, not a raw row delete.

- Metrics Source and Alertmanager require all canonical scope bindings to be removed first.
- Kubernetes removes only bindings that target the deleted cluster; reusable Metrics Source and Alertmanager source instances remain intact.
- Active validation, runtime, analytics, forecasting, or maintenance jobs block deletion while they still reference the provider or Kubernetes scope.
- Kubernetes deletion is also blocked while Protected Secret Reveal requests remain `pending` or `approved`.
- Generated reports and schedules are detached and retained. Runtime observations, canonical JobExecution history, and Activity Audit evidence remain available under their own lifecycle policies.
- The manage workspace must show the remove/retain boundary and current blockers before enabling a destructive action.

## Inventory & Operational Use

The Kubernetes lifecycle workspace uses one full-width information block before the danger zone. It must expose:

- compact inventory, capability, binding, and reporting metrics;
- the KAORI domains that consume the connection;
- the effective Metrics Source and Alertmanager source bindings;
- the exact data removed with the registration;
- the historical and reusable records retained after deletion.

The destructive control remains in a separate `Connection Lifecycle` block so operational context is readable before the user reaches the delete action.

## Technical Check Presentation

Metrics Source and Alertmanager expose executable provider expressions inside expandable **Technical Checks**. Kubernetes follows the same disclosure pattern and provides a runnable `kubectl` shell script that verifies API serving, resource discovery, effective RBAC, and a bounded live read. Explanatory evidence remains normal KAORI typography; only runnable queries, requests, or scripts use monospace and Copy.

### Operational Domain Readiness Interpretation

The Metrics Source Analytics Readiness workspace must explain the difference between an individual Technical Check and a complete consumer contract directly inside Operational Domain Readiness.

- A successful Technical Check proves only that one registered PromQL query executed.
- Domain readiness additionally requires the complete metric, label, identity, and pairing contract consumed by the Analytics module.
- The Storage Filesystem Contract requires both `node_filesystem_size_bytes` and `node_filesystem_avail_bytes` for the same canonical node identity and mountpoint. `/var` is preferred and `/` is the documented fallback.
- The canonical node identity is exactly `node=<Kubernetes Node.name>`. Legacy aliases such as `nodename` or `kubernetes_node`, and `instance` endpoint identity, do not satisfy Storage Analytics readiness.
- Users must be directed to Analytics Query Contract Evidence for the exact validation queries, observed labels, and remediation guidance.
