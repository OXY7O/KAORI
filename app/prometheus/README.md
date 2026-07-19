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

`Test Connection` remains intentionally fast. `Run Full Validation` is the explicit long-running operation and must provide operational toast feedback.

## Field ownership

- `endpoint_product`: `prometheus` or `thanos`.
- `detected_version`: runtime version of the endpoint KAORI contacts.
- `compatibility_profile`: compatibility profile of that endpoint product.
- `source_prometheus_major`: Prometheus source contract used for PromQL selection.
- `query_profile`: versioned PromQL contract.
- `readiness_status`: final Kubernetes Analytics readiness.

All PromQL is owned by `app/prometheus/query_profiles`. Legacy domain `queries.py` modules are compatibility exports only. See `docs/PROMQL_QUERY_PROFILES.md` for metadata, validation, retention, deprecation, and replacement rules.

Runtime versions must come from endpoint APIs. Helm chart versions and chart app metadata are deployment metadata only and must never be used as binary compatibility evidence.


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

Prometheus is the second provider using the shared Integration Runtime Framework. Manual Full Validation and scheduled monitoring use the same runtime adapter, health scoring, rolling 100-record observation retention, and history model.

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

Storage readiness is validated with the same PromQL contract used by Storage Analytics. KAORI no longer marks the filesystem capability as misconfigured solely because a bounded `/series` discovery sample does not report a canonical node label. The exact `/var` query, with `/` as fallback, is authoritative.

The Analytics Readiness panel exposes Expected, Observed, Technical Evidence, validation query, possible causes, and remediation. Metric availability remains visible as troubleshooting evidence but does not override a successful feature query contract.

## Cluster-bound runtime and authoritative query contracts

The current Prometheus integration is bound to a Kubernetes cluster rather than managed as a free-standing provider instance. It still uses the shared Integration Runtime adapter, observation, history, health-scoring, and presentation contracts used by Alertmanager.

Runtime view models own route URLs and binding labels. Prometheus templates must not access `cluster.id` to build refresh actions. Full Validation executes the exact registered Kubernetes Analytics queries and stores a feature-contract summary. The resulting contract summary is authoritative for `query_validation_status` and Analytics readiness; metric-name and recent-series schema discovery remain technical diagnostics.


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

Alertmanager and Prometheus opt into the `kaori-integration-semantic` scope. Within this scope, Primary Violet is limited to navigation, primary action, focus, selection, and KAORI identity. Operational state uses Normal, Info, Warning, Critical, or Neutral. Compact labels are rectangular and borderless; semantic border tokens are reserved for panels, callouts, dialogs, and controls.

