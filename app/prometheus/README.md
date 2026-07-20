# Prometheus and Thanos query integration

Prometheus compatibility exists to protect **Kubernetes Analytics**, dashboard live metrics, Prometheus-backed reports, and Prometheus-backed intelligence. It is separate from Kubernetes API compatibility and Alertmanager API compatibility.

## Compatibility modes

### Automatic: direct Prometheus

`KAORI -> Prometheus`

KAORI reads `/api/v1/status/buildinfo`, stores the Prometheus endpoint runtime, matches the Prometheus compatibility profile, and selects the corresponding PromQL profile. The current profiles are:

- `prometheus-http-v2` -> `promql-kubernetes-v1`
- `prometheus-http-v3` -> `promql-kubernetes-v1`

### Manual: Thanos Query intermediary

`KAORI -> Thanos Query -> Prometheus`

KAORI stores two distinct identities:

- the Thanos Query endpoint runtime and Thanos compatibility profile;
- the administrator-selected Prometheus source profile used to select the PromQL contract.

A Thanos version must never be displayed or persisted as a Prometheus version. The manual source selection does not make the integration ready by itself. Full validation must still verify required metrics, label schemas, versioned PromQL, and historical coverage.

## Validation lifecycle

1. Save configuration -> `validation_required`.
2. Test Connection -> query endpoint, detect endpoint identity, match endpoint profile, resolve Prometheus source profile, select PromQL profile.
3. Run Full Validation -> metric discovery, label-schema checks, PromQL audit, and retention probes.
4. Consumers may use the integration only when analytics readiness permits it.

`Test Connection` remains intentionally fast and synchronous because registration needs an immediate proof. `Run Full Validation` is queued to the dedicated `integration-validation` Celery worker. The Flask request returns after enqueueing, the workspace polls through HTMX, and queued/completed/failed lifecycle events are written to Activity Audit Log and surfaced through the persistent KAORI toast.

## Field ownership

- `endpoint_product`: `prometheus` or `thanos`.
- `detected_version`: runtime version of the endpoint KAORI contacts.
- `compatibility_profile`: compatibility profile of that endpoint product.
- `source_prometheus_major`: Prometheus source contract used for PromQL selection.
- `query_profile`: versioned PromQL contract.
- `readiness_status`: final Kubernetes Analytics readiness.

All PromQL is owned by `app/prometheus/query_profiles`. Legacy domain `queries.py` modules are compatibility exports only. See `docs/PROMQL_QUERY_PROFILES.md` for metadata, validation, retention, deprecation, and replacement rules.

Runtime versions must come from endpoint APIs. Helm chart versions and chart app metadata are deployment metadata only and must never be used as binary compatibility evidence.


## Worker execution contract

Prometheus validation uses the following execution boundary:

- registration `Test Connection`: synchronous lightweight request;
- `Refresh Runtime`: asynchronous lightweight worker job;
- `Run Full Validation`: asynchronous heavy worker job;
- binding `Validate`: asynchronous scope-isolated worker job.

The UI disables duplicate actions while a task lock exists and polls the task-specific status endpoint every 1.5 seconds. Full Validation and Runtime Refresh do not run concurrently for the same Prometheus instance. The worker records completion or failure to Activity Audit Log and returns sanitized toast feedback; credentials and raw query payloads are never placed in task metadata.

## Full validation performance and readiness

Full validation is intentionally broader than a connectivity check, but it must remain bounded. KAORI performs one metric-name discovery, batched recent-series schema checks, and four historical probes. It no longer sends one `/api/v1/series` request per query. Optional analytics domains may report partial coverage without forcing the global Kubernetes Analytics readiness to `Degraded`; only core dashboard, capacity, and utilization contract failures affect the global readiness. The configuration page refreshes readiness through an HTMX out-of-band swap after test or validation completion.

### Readiness evidence presentation

Full Validation stores a compact `blocked_details` list in `query_validation_summary` for user-facing readiness diagnostics. Each entry records the blocked query key, analytics domain, validation message, and missing metric or label evidence. The Prometheus Configuration page displays this evidence separately from the domain-level summary so operators can identify the exact contract that requires remediation without exposing the full internal audit payload.

## Capability-first runtime validation

KAORI treats the endpoint visible at the configured URL as the runtime endpoint. When the URL points to Thanos Query, `detected_version` is the Thanos version and the Prometheus backend version may remain unobservable. Version and compatibility profiles are advisory; observed query, metric, label, and retention capabilities are authoritative.

Full validation must prove the complete query contract used by Analytics. A metric being present is insufficient when required labels are absent or cannot be correlated with Kubernetes objects. In particular, filesystem metrics that expose only `instance="IP:port"` are recorded as `Storage Node Identity Mapping: Misconfigured`; Storage Analytics must not silently claim full readiness. Operators must provide a canonical `node`, `nodename`, or `kubernetes_node` label through scrape relabeling or recording rules.

Each unavailable capability exposes:

- status and observed evidence;
- affected KAORI modules;
- operational impact;
- expected metrics, labels, API, or payload fields;
- source owner;
- concrete remediation and an optional validation query.

Prometheus uses the shared Integration Runtime Framework with two distinct worker operations. Manual Full Validation rebuilds metric, label, PromQL, retention, capability, and module-readiness evidence. Scheduled Runtime Health Refresh performs only the lightweight `vector(1)` and endpoint-identity checks, preserves the latest full-validation evidence, and appends the rolling runtime observation. Both operations run on the dedicated validation worker, but scheduled monitoring does not repeat the full query audit every five minutes.

## Consumer boundary

`app/prometheus/consumer.py` is the canonical read boundary for Kubernetes
Analytics and other authorized operational consumers. It accepts a cluster context, resolves the
configured Prometheus or Thanos Query endpoint, checks integration readiness and
required capabilities, and only then executes the query.

The endpoint product is intentionally transparent to analytics. A query may be
served by direct Prometheus or Thanos Query, but the consumer exposes one source
contract containing endpoint product, compatibility profile, capability profile,
readiness, and runtime health.

Confirmed missing or misconfigured capabilities block only operations that
explicitly require them. A migrated configuration without a capability snapshot
remains temporarily compatible when its readiness is already `ready`; rerunning
full validation replaces that compatibility behavior with authoritative
capability evidence.

## Storage feature-contract validation

Storage readiness is validated from the same selectors used by Storage Analytics. The validator wraps the `/var` and `/` size/available selectors in a low-cardinality `count by (node, nodename, kubernetes_node, mountpoint)` probe, then requires at least one matching size/available identity pair. This preserves the authoritative mount and node contract while avoiding a large label-heavy response from shared or multi-cluster endpoints.

Full Validation uses an extended provider read timeout for the query audit while Test Connection and Runtime Refresh remain lightweight. The Analytics Readiness panel exposes the effective validation expression, registered selector, response-series count, matching-pair evidence, endpoint error or timeout, possible causes, and remediation. Metric discovery remains troubleshooting evidence but does not override a successful feature contract.

## Reusable instances, cluster bindings, and authoritative query contracts

Prometheus-compatible endpoints are registered as reusable provider instances and associated with managed Kubernetes clusters through provider-neutral scope bindings. A connection may exist, be tested, and be validated before any cluster binding is assigned. Cluster-bound configuration and Analytics consumers resolve the effective eligible instance for the selected cluster.

Runtime view models own route URLs and binding labels. Shared runtime partials must not depend on a cluster object to build instance actions. Full Validation executes the exact registered Kubernetes Analytics queries and stores a feature-contract summary. The resulting contract summary is authoritative for `query_validation_status` and Analytics readiness; metric-name and recent-series schema discovery remain technical diagnostics.


## Query validation failure isolation

Full Validation executes registered PromQL checks independently. A rejected query is stored as contract evidence and must not abort the complete validation run. Runtime-bound query templates containing placeholders such as `__TIME_RANGE__` and `__TIME_STEP__` are marked deferred during instant validation rather than being sent to the endpoint unchanged.

HTTP error evidence includes the Prometheus-compatible endpoint error type and message when available. Analytics Readiness technical detail displays the exact registered query, response-series count, and endpoint rejection detail.

## KAORI Violet integration workspace contract

Prometheus uses the same provider-neutral workspace concept as Alertmanager while retaining metrics-specific terminology and operations.

- The landing page contains a standardized KAORI hero, integration overview, HTMX connection registry, readiness filters, scope coverage, and registration action.
- The instance detail page is divided into `Configuration`, `Validation & Capabilities`, `Runtime & History`, and `Scope & Resolution` domains.
- Configuration establishes endpoint identity, authentication, TLS, timeout, and compatibility-detection behavior.
- Test Connection verifies endpoint reachability and identity. Full Validation evaluates API compatibility, metric/label contracts, PromQL execution, retention evidence, capability readiness, and dependent operational domains.
- Runtime evidence uses the shared health model and rolling 100-record retention. Scope bindings determine which operational consumers may resolve the connection.
- Prometheus and Thanos remain authoritative for scraping, rules, query execution, retention, federation, and historical storage. KAORI provides validation, governance, correlation, runtime evidence, and controlled source resolution.

The KAORI semantic color contract applies globally. Primary Violet is limited to navigation, primary action, focus, selection, and KAORI identity. Operational state uses Normal, Info, Warning, Critical, or Neutral. Compact labels are rectangular and borderless; semantic border tokens are reserved for panels, callouts, dialogs, inputs, and destructive controls.



### Global semantic color contract

This workspace consumes the shared KAORI palette and label components. Provider templates must not introduce a separate status palette. Pending maps to Info, maintenance to Warning, and disabled/unknown to Neutral.

## Prometheus Manage UI and lifecycle contract

Prometheus administration follows the same KAORI workspace contract used by Alertmanager while preserving metrics-specific operations.

### Workspace structure

- `Configuration`, `Validation & Capabilities`, `Runtime & History`, and `Scope & Resolution` use one shared tab treatment with Title Case labels, contextual badges, and accessible `tablist` semantics.
- Each domain begins with three peer-level Violet `Workspace Summary Card` components. A semantic warning or critical panel is added separately only when the state itself requires emphasis.
- Primary ordered workflows use the shared `Info Flow` component. Supporting runtime interpretation uses the shared `Health Interpretation` component rather than provider-local gauges or score markup.
- The provider landing page remains a registry and portfolio view. Destructive lifecycle actions are placed in the instance detail workspace, not in the hero or landing table.

### Instance deletion

A registered Prometheus instance can be deleted from:

`Prometheus Instance Detail → Scope & Resolution → Instance Lifecycle & Deletion`

Deletion is intentionally governed:

1. Every provider-neutral scope binding must be removed first, including disabled bindings.
2. KAORI displays a critical confirmation modal; browser `confirm()` prompts are not permitted.
3. The provider record and canonical `IntegrationInstance` identity are deleted in one database transaction.
4. Historical runtime observations and Activity Audit records remain available.
5. Deletion does not call the Prometheus or Thanos endpoint and therefore does not depend on live provider availability.

The delete button is disabled while bindings remain, and the service layer repeats the same blocker check so direct POST requests cannot bypass the lifecycle boundary.

### Provider landing and registration alignment

Prometheus follows the same provider-neutral visual hierarchy as Alertmanager:

- the landing Hero owns the single registration action;
- the registry owns the single scope-management action;
- overview cards do not duplicate either action;
- registration uses a compact Hero Context Panel, primary Info Flow, Compatibility Detection Information Guide, After Registration guidance, and an intrinsic-height Related Analytics Workspace card.

Compatibility Detection choices distinguish a direct Prometheus endpoint from a Prometheus-compatible gateway such as Thanos Query. Detection or manual declaration identifies the compatibility contract only; Full Validation remains authoritative for capability and readiness evidence.

Instance detail pages must not fail because an optional lifecycle endpoint is absent in a partial deployment. Lifecycle URLs are built in the route context through a registered-endpoint check. Missing endpoint registration is logged and rendered as an unavailable action rather than raising a Jinja `BuildError`.

## Manage workspace parity with Alertmanager

The registered Prometheus instance page follows the Alertmanager reference architecture. Configuration is edited inline; the legacy edit route redirects to the Configuration tab. Validation always exposes the complete Prometheus capability catalog with technical probes, evidence, success criteria, required configuration, dependent domains, and remediation. Runtime uses the shared Health Interpretation, Diagnostic Pipeline, and rolling observation history. Scope & Resolution supports inline binding creation/removal and consumer-specific source-resolution evidence.

All full-page and HTMX partial responses use one manage-workspace context builder. Test Connection, Full Validation, and Runtime Refresh synchronize the provider record back to the canonical integration identity so resolver decisions use current readiness and health.

## Operational action feedback

Prometheus normal-flow mutations use HTMX, persist one Activity Audit event, and return matching out-of-band toast feedback. Configuration, validation, runtime refresh, binding changes, and rejected deletion remain on the current manage tab. Successful registration and instance deletion use `HX-Redirect`. Cluster compatibility routes are not linked by normal provider UI.

## Shared-source binding and metrics-isolation contract

Prometheus and Prometheus-compatible endpoints are connection resources, not one-record-per-cluster configuration. The supported operational flow is:

1. Register the endpoint once in the Prometheus registry.
2. Open `Integration Coverage` or a Kubernetes integration row and choose `Bind Source`.
3. Select an existing enabled provider instance.
4. Define the metrics identity selector exposed by that source, for example `cluster="k8s-production"`.
5. Validate the binding from `Scope & Resolution` before Analytics may resolve it.

The provider instance continues to own endpoint URL, credentials, TLS, timeout, detected product/version, compatibility profile, runtime capability evidence, and health history. `IntegrationBinding` owns scope identity, role, priority, capability coverage, selector matchers, and binding-validation evidence. Binding a second cluster does not duplicate the provider instance or its credentials.

`app/integrations/binding_selectors.py` is the provider-neutral selector boundary. `PrometheusClient` applies the selected binding matcher to instant queries, range queries, point-in-time queries, and `/series` matchers. A query that already contains a conflicting matcher for the identity label is rejected rather than widened or silently rewritten. This prevents one Kubernetes scope from reading another scope through a shared endpoint.

A newly saved binding has `validation_required` status and is not eligible for source resolution. Kubernetes binding validation executes a scoped `count(kube_node_info)` probe:

- `ready`: one or more scoped node series were observed;
- `degraded`: the selector was accepted but no scoped node series were observed;
- `blocked`: selector configuration, endpoint execution, authentication, or query processing failed.

Migrated bindings are marked `legacy_unscoped`. A single legacy binding remains temporarily eligible for compatibility. As soon as the same canonical provider instance has more than one enabled binding, every binding must have a selector; unscoped legacy bindings are blocked from resolution until their selector is configured in place and validated.

Normal-flow routes:

- `GET|POST /integrations/prometheus/bind?scope_key=<cluster-id>` selects and binds an existing source.
- `POST /integrations/prometheus/instances/<instance-id>/bindings/<binding-id>/selector` configures or replaces the metrics identity without deleting the binding.
- `POST /integrations/prometheus/instances/<instance-id>/bindings/<binding-id>/validate` validates scope isolation.
- Provider registration remains a secondary action used only when no suitable endpoint has been registered.

The current first-class binding workspace is implemented for managed Kubernetes clusters. The canonical selector schema is provider-neutral and can also represent server, server-group, HCI, storage, or global scopes when those asset registries and provider adapters are introduced.
