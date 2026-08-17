# Versioned PromQL query profiles

KAORI does not permit PromQL to be added directly to routes, templates, or service methods. For Metrics Source providers using PromQL, every query is registered under a stable key in `app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py` and consumed directly from the canonical query-profile registry by Analytics, Dashboard, Reports, Notifications, and Intelligence.

## Current profile

- Profile: `promql-kubernetes-v1`
- Prometheus API family: Prometheus 2.x HTTP API v1
- Thanos query family: Thanos Query implementing the Prometheus HTTP v1 API
- Registered queries: 161
- Source domains: core Prometheus, alerts, capacity, forecast, storage, top consumers, utilization, and workload analytics

Each `QueryDefinition` declares:

- stable query key;
- PromQL expression;
- owning domain;
- required metrics;
- required labels per metric selector;
- required historical horizon where relevant;
- deprecation version;
- replacement query key;
- technical notes.

Domain services resolve stable query keys from the canonical registry. Provider-local and analytics-local `queries.py` export facades are removed so independent PromQL ownership cannot reappear.

## Validation lifecycle

`PromQLProfileAuditor` validates:

1. metric-name availability through `/api/v1/label/__name__/values`;
2. label schema through `/api/v1/series`;
3. optional execution of every registered query;
4. 24-hour, 7-day, 30-day, and 60-day history availability;
5. deprecated query and replacement metadata.

A compatible Metrics Source endpoint using the Prometheus HTTP adapter can still be `degraded` when required exporters, metrics, labels, or historical data are missing. Query readiness is therefore separate from engine compatibility.

## Retention and Thanos

The Helm output must not be used as the Prometheus binary version. In the supplied estate:

- `kube-prometheus-stack-87.10.1` is a Helm chart version;
- chart app version `v0.92.1` is deployment metadata and is not accepted as the Prometheus server version;
- `thanos-17.3.1` is the Thanos Helm chart version;
- app version `0.39.2` identifies the Thanos application family, not Prometheus.

KAORI must detect the Prometheus server runtime from `/api/v1/status/buildinfo`. Thanos must be validated separately as a Prometheus-compatible query backend. Historical readiness is measured against the endpoint actually used for long-range queries. A local Prometheus endpoint can be healthy while failing the 30-day or 60-day horizon; that is not evidence that Thanos retention is unavailable unless KAORI is querying the Thanos endpoint.

## Deprecation and replacement

Query deprecation and replacement metadata remains attached to `QueryDefinition`, allowing the canonical profile registry to resolve a replacement without editing every consumer. Provider API lifecycle data remains in each provider capability profile rather than a cross-product compatibility facade.

Current queries use the kube-state-metrics v2 resource/unit metric shape. Legacy typed metrics such as `kube_pod_container_resource_requests_cpu_cores` are not used.

## Adding or changing a query

1. Add a new `QueryDefinition` under a new or existing profile.
2. Declare required metrics and labels.
3. Set `deprecated_since` and `replacement_key` when replacing an old definition.
4. Keep the old stable key until all consumers have migrated.
5. Run metadata validation and full query execution against each supported estate profile.
6. Update this document and the compatibility matrix.

## Alerts & Anomalies Query Contract

The Alerts query family is defined in `query_profiles/alerts_v1.py` and registered under stable `analytics.alerts.queries.*` keys in the Kubernetes v1 profile. Active alerts include `pending|firing`. Restart and readiness anomalies only evaluate Pods in `Pending|Running`. Restart counters are normalized with `max by(namespace,pod,container)` before Pod aggregation, and readiness is normalized by `namespace,pod`.

Restart and readiness are separate feature contracts. Runtime collection executes them independently and reports partial evidence when only one family succeeds. Query-profile consumers must not embed replacement PromQL in routes, services, reports, or templates.

## Capacity Ready-Worker Query Contract

Capacity query definitions use the `analytics.capacity.queries.WORKER_*` family only. Every schedulable CPU, memory, pod, request, limit, current-usage, and peak-usage expression excludes `control-plane|master` roles and intersects the remaining series with `kube_node_status_condition{condition="Ready",status="true"} == 1`. Request and limit metrics must expose `namespace`, `node`, `pod`, `resource`, and `unit`; without the node label KAORI cannot enforce the worker boundary and the capability remains incomplete.

Node filesystem expressions are reused from the canonical Utilization query registry as optional operational reference evidence. They are not part of Kubernetes allocatable capacity and cannot block the Capacity scheduling contract. Unscoped legacy Capacity query definitions are not retained.

## Storage Analytics Evidence Contract

Storage Analytics registers one query per signal. Filesystem pressure requires a matching size and available-byte pair for `/var` or fallback `/`. PVC pressure uses `kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes`; requested claim bytes are a separate demand signal. Capacity, used, and available PVC gauges use `max by (namespace, persistentvolumeclaim)` so duplicate kubelet scrape targets do not inflate the value. Missing query results remain unavailable evidence rather than synthetic zero.

## Workload Analytics query boundary

Workload Analytics uses the `kubernetes-v1` query family with these invariants:

- active scope is limited to Pods in `Pending|Running`;
- request, limit, current usage, owner, and QoS signals are joined on `namespace,pod` with that active-Pod set;
- container gauges/rates are deduplicated with `max by(namespace,pod,container)` before Pod or Namespace aggregation;
- active Pod counts use `kube_pod_status_phase`, not unscoped `kube_pod_info`;
- ResourceQuota hard/used evidence keeps `namespace,resourcequota,resource,type` and uses `max` to normalize duplicate scrape copies;
- selected-window peak templates preserve the same active-Pod and duplicate-series boundary inside the subquery.

Consumers must not flatten multiple ResourceQuota objects into one namespace/resource map. Query-profile label validation requires ResourceQuota object identity and active-Pod phase labels.

## Forecast Analytics boundary

Forecast query profiles use the longest supported history declaration (`required_history='90d'`). CPU, memory, and Pod demand are joined to Pod node identity, restricted to Ready workers, and exclude both `control-plane` and legacy `master` roles. Container and Pod gauges are normalized with `max by` over canonical identities before summation. Active Pod demand includes `Pending|Running`.

Storage Forecast uses `kubelet_volume_stats_used_bytes` divided by `kubelet_volume_stats_capacity_bytes`. Duplicate scrape samples are normalized with `max by(namespace,persistentvolumeclaim)` before aggregation. Namespace variants filter both usage and capacity to the selected Namespace. Forecast capability validation covers CPU, memory, Pods, and Storage inputs.
## Top Consumers query boundary

Top Consumers uses current active workload and observed volume evidence with these invariants:

- CPU and memory rates/gauges are normalized with `max by(namespace,pod,container)` before ranking or summation;
- compute usage, requests, limits, and Pod ownership are joined to Pods in `Pending|Running`;
- Pod density counts distinct `Running` Pods by Namespace;
- CPU, memory, and Pod capacity intersect Ready nodes and exclude `control-plane|master`;
- PVC usage and capacity use `max by(namespace,persistentvolumeclaim)` to avoid duplicate kubelet scrape inflation;
- PVC pressure uses `kubelet_volume_stats_capacity_bytes`, never requested claim bytes;
- cluster and Namespace query variants preserve identical identity and denominator semantics.

Runtime transport requires instant-query capability. Domain capability observations remain advisory: when an advisory capability is missing and its exact query returns no series, KAORI preserves Unavailable evidence instead of interpreting the result as confirmed zero or a confirmed configuration gap.
