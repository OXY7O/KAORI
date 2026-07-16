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
