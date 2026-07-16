# Versioned PromQL query profiles

KAORI does not permit PromQL to be added directly to routes, templates, or service methods. Every query is registered under a stable key in `app/prometheus/query_profiles/kubernetes_v1.py` and consumed through the compatibility export modules already imported by Analytics, Dashboard, Reports, Notifications, and Intelligence.

## Current profile

- Profile: `prometheus-kubernetes-v1`
- Prometheus API family: Prometheus 2.x HTTP API v1
- Thanos query family: Thanos Query implementing the Prometheus HTTP v1 API
- Registered queries: 171
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

The existing `queries.py` modules are now compatibility exports. They no longer own independent PromQL strings, which prevents silent drift between pages.

## Validation lifecycle

`PromQLProfileAuditor` validates:

1. metric-name availability through `/api/v1/label/__name__/values`;
2. label schema through `/api/v1/series`;
3. optional execution of every registered query;
4. 24-hour, 7-day, 30-day, and 60-day history availability;
5. deprecated query and replacement metadata.

A compatible Prometheus binary can still be `degraded` when required exporters, metrics, labels, or historical data are missing. Query readiness is therefore separate from engine compatibility.

## Retention and Thanos

The Helm output must not be used as the Prometheus binary version. In the supplied estate:

- `kube-prometheus-stack-87.10.1` is a Helm chart version;
- chart app version `v0.92.1` is deployment metadata and is not accepted as the Prometheus server version;
- `thanos-17.3.1` is the Thanos Helm chart version;
- app version `0.39.2` identifies the Thanos application family, not Prometheus.

KAORI must detect the Prometheus server runtime from `/api/v1/status/buildinfo`. Thanos must be validated separately as a Prometheus-compatible query backend. Historical readiness is measured against the endpoint actually used for long-range queries. A local Prometheus endpoint can be healthy while failing the 30-day or 60-day horizon; that is not evidence that Thanos retention is unavailable unless KAORI is querying the Thanos endpoint.

## Deprecation and replacement

Cross-product API and metric deprecations are stored in `app/integrations/deprecations.py`. Query-specific deprecations remain attached to `QueryDefinition` so a profile can resolve a replacement without editing every consumer.

Current queries use the kube-state-metrics v2 resource/unit metric shape. Legacy typed metrics such as `kube_pod_container_resource_requests_cpu_cores` are not used.

## Adding or changing a query

1. Add a new `QueryDefinition` under a new or existing profile.
2. Declare required metrics and labels.
3. Set `deprecated_since` and `replacement_key` when replacing an old definition.
4. Keep the old stable key until all consumers have migrated.
5. Run metadata validation and full query execution against each supported estate profile.
6. Update this document and the compatibility matrix.
