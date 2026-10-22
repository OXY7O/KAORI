# Vault Metrics Source binding — HV-06 (#2590)

## Authority and registered source

Vault is authoritative for Secret/PKI/lifecycle facts; Vault telemetry is
scraped by Prometheus (optionally queried through Thanos for long retention).
KAORI does **not** implement a Vault-specific TSDB or copy metrics into KV v2
inventory. Its Metrics Source registry remains responsible for connection
validation, selector binding, query.instant/query.range and source routing.
The source is configured in `Integrations → Observability → Metrics Source`,
not on an embedded Vault telemetry dashboard.

## Vault scrape prerequisites

For supported Vault installations, configure Prometheus with:
- HTTPS target and approved CA/trust; `metrics_path: /v1/sys/metrics`.
- Appropriate read-only token custody in the Prometheus scrape configuration,
  not inside KAORI ordinary evidence or Git.
- Prometheus relabel/static target label `vault_instance: "<KAORI IntegrationInstance.id>"`
  where the value is the numeric KAORI canonical Vault provider identity.
- A qualified `vault_core_active` gauge that is query-visible at the selected
  Prometheus/Thanos source and has a bounded sample age.

HashiCorp `/sys/metrics` requires the **root namespace**. Active/standby
and CE/Enterprise behavior differ; a working Vault health API does not imply
scrape permissions or metrics on every node. Verify the scrape is actually
exposed and matches the supported metric naming profile.

Official source references:
- https://developer.hashicorp.com/vault/api-docs/system/metrics
- https://developer.hashicorp.com/vault/docs/configuration/telemetry
- https://developer.hashicorp.com/vault/docs/internals/telemetry/metrics/core-system

## First admitted review contract

The existing Metrics Source Managed Asset type `vault_instance` is bound to
one canonical IntegrationInstance ID. The `prometheus_http` adapter now
registers `vault-telemetry-v1` with the ordinary `binding.validate` path.

The current one-matcher form requires exactly:
`vault_instance=<numeric IntegrationInstance.id>` with `=` operator.
The validator issues only a bound, read-only
`vault_core_active{vault_instance="<id>"}` query and qualifies exactly one
0/1 signal whose sample is no older than five minutes. Zero series are
**degraded**, multiple series with the same Vault instance identity are
**blocked as ambiguous**, and target-name/regex matching is not accepted as
equivalent to canonical provider identity.

This strict profile does not claim complete HA cluster coverage. Multi-target
HA profiles must use additional independently qualified node/cluster
selectors, explicit freshness and retention and their own accepted binding
validation. A single matching standby gauge is an identity signal, not
proof of Vault availability or active leadership.

**Not yet delivered:** historical range/retention qualification, source-owned
metrics history/materialization, Vault-specific Analytics queries, Alert Source
binding to canonical alert instances, HA/federation profiles and real
Prometheus/Thanos UAT. None of these optional telemetry gaps can downgrade
core Vault API readiness. The Vault operational Overview continues to show
missing metrics as **not bound/not materialized** until approved read models
exist.

Focused tests authored:
`tests/integrations/test_vault_metrics_binding.py`.

Use existing KAORI validation and security gates, including Prometheus/Thanos
negative tests, per-source label/scope checks, Developer Check and real
DevContainer UAT. No readiness PASS has yet been observed.
