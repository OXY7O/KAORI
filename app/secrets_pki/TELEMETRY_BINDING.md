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

**Not yet delivered:** qualified multi-day/long-term retention,
source-owned metrics history/materialization, Vault-specific Analytics queries,
HA/federation profiles, AlertCase enrichment/routing and real Prometheus/Thanos
UAT. The independently validated recent-hour source probe described below
must not be mistaken for a materialized historical dataset. None of these
optional telemetry gaps can downgrade core Vault API readiness. The Vault operational Overview continues to show
missing metrics as **not bound/not materialized** until approved read models
exist.

Focused tests authored:
`tests/integrations/test_vault_metrics_binding.py`.

Use existing KAORI validation and security gates, including Prometheus/Thanos
negative tests, per-source label/scope checks, Developer Check and real
DevContainer UAT. No readiness PASS has yet been observed.


## Vault Alert Source / Alertmanager consumer (HV-06 follow-up)

The existing Alertmanager provider owns API v2 alert retrieval, silences,
routing, grouping and source readiness. The canonical `IntegrationBinding`
for `vault_instance` uses the `vault-alerts-v1` profile. In the
Alertmanager Bindings & Consumers workspace, select the canonical Vault
instance and configure the exact equality matcher:

```text
vault_instance="<KAORI IntegrationInstance.id>"
```

Use the **same** `vault_instance` value on the Prometheus/Alertmanager rule
labels for that Vault deployment. It is not supplied by Vault automatically.
A healthy Alertmanager API with zero active matching alerts is not evidence
that Vault has no failures: `identity_observed=false` remains explicit.
Other Vault instances and global unmatched alerts must not be attributed
to the selected asset.

The source binding is validated on creation/update and again at runtime.
Unknown or retired Vault instances, regex/broad/noncanonical selectors
and foreign alert labels are blocked. The Vault binding stores counts and
capability flags but suppresses sample alert names, which may themselves
contain sensitive Secret paths. Provider failure messages are sanitized.

Alertmanager source eligibility is **independent** of the Vault API,
KV v2 collection state, and Prometheus historical coverage. Binding alone
does not create new Prometheus alerting rules, AlertCases, enrichment,
receiver routing, webhook paths or an alert notification engine. Those
are covered by the existing Central Alert Intelligence and #2596.

Required UAT: register approved Alertmanager source, bind and validate an
approved Vault instance with no alerts and a representative matching
alert, reject mismatched identities, confirm per-role direct access
and ensure provider outage does not mutate Vault readiness. Do not
declare binding acceptance without those checks.

Focused tests:
`tests/integrations/test_vault_alert_source_binding.py`.

Provider API source: https://github.com/prometheus/alertmanager/blob/main/api/v2/openapi.yaml


## Bounded historical query-range qualification — HV-06 #2697

An explicit Vault Metrics Source **Validate Binding** now first qualifies the
existing exact single-node instant `vault_core_active` identity. If that succeeds,
the same registered Prometheus-compatible client requests **one** bounded
`query_range` over the most recent 60 minutes at a 300-second step.

The validator checks exact `vault_instance` identity, one matrix series,
finite/monotonic timestamp and 0/1 values, endpoint coverage and no gap
exceeding ten minutes. It retains only sanitized evidence status/count/step:
`recent_hour_qualified`, `incomplete`, `ambiguous`, `unavailable`, or
`not_validated`. A qualified recent hour stores
`retention_coverage=one_hour_observed_only` and **does not establish**
historical retention beyond that hour, HA topology, continuous workload
health, Vault API availability, service impact or time-series materialization.

Range unavailable/denied/malformed/missing never upgrades retention, but
also **does not downgrade** already-qualified instantaneous identity nor core
Vault provider readiness. No provider tokens, host/metric label values,
timeseries points or raw response/errors are committed. Prometheus/Thanos
remains authoritative; no new TSDB/worker/query endpoint is introduced.
Existing binding validation evidence ownership remains unchanged.

The real Prometheus/Thanos range API, worker/network performance, HA and
long-term retention require DevContainer/staging UAT. Test source:
`tests/integrations/test_vault_metrics_binding.py`.

## Committed binding-coverage projection (HV-06 #2767)

The Secrets & PKI **Operational Overview** no longer unconditionally labels
Vault Metrics and Alert sources as `Not Bound`. The bounded read-only
`build_vault_binding_coverage` reads canonical `IntegrationInstance` and
`IntegrationBinding` records, never calls Prometheus/Thanos or Alertmanager
during HTTP rendering, and emits only source-neutral summary labels/counts.

For active approved Vault instances (max 25, binding rows max 100), it
qualifies **one** source binding per instance only when:
- `asset_type=vault_instance` and `asset_key` exactly equals the canonical
  `IntegrationInstance.id` decimal string;
- the source IntegrationInstance is active, enabled and in its own
  `metrics_source` / `alert_source` integration family;
- validation profile is `vault-telemetry-v1` / `vault-alerts-v1`;
- validation status is `ready`, timestamp is not in the future and no older
  than 24 hours; multiple independently ready bindings are not counted as
  single-source qualification.

Stale/disabled/incomplete/unbound/error states are **not qualified**.
Qualification here means **committed identity binding validation**, NOT
live health, complete HA/federation coverage, historical Metrics Source
retention, observed alert absence, AlertCases, routing or delivery success.
Source IDs, selectors, raw alerts, Secret names, paths, Vault credentials
and provider response payloads never enter this fleet-level view.
Source-specific drilldown continues to require each Integration capability's
existing authorization. Exact-SHA DevContainer tests/UAT remain required.

## HV-12 bounded Vault source alert evidence (#2786)

During the existing **explicit Alert Source Validate Binding**, the canonical
Alertmanager provider now evaluates up to 100 returned Vault alert rows. Each
must carry the exact approved `vault_instance` identity. The only committed
additional metadata is a safe, allowlisted `vault_alert_sample` evidence
record: sample state and counts grouped by Alertmanager active/suppressed/
unprocessed status and critical/warning/info severity.

An empty response is `unobserved`, with unknown counts; an invalid source
identity, unexpected response shape or over-budget row population is `blocked`.
Missing/unrecognized lifecycle or severity evidence is `incomplete` and
downgrades only consumer binding validation. Partial counts are discarded.
Sensitive alert names, paths, labels, annotations, fingerprints, URLs,
credentials and source responses are never committed by this new summary.
Previous evidence is cleared on blocked validation.

This is a **point-in-time binding-validation sample**, never a live AlertCase,
current firing/silence count, confirmed health, root cause, service impact,
recovery, escalation or successful notification. There is no polling, new
runtime read path, AlertCase promotion, alert routing, provider mutation or
implicit cross-tenant authorization. Later HV-12 work requires separate
governed committed source snapshots, case ownership and access controls.
Focused tests: `tests/integrations/test_vault_alert_source_qualification.py`.
Exact-SHA local and provider DevContainer UAT remain required.
