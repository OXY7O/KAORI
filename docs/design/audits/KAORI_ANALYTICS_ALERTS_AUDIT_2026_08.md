# KAORI Analytics Alerts & Anomalies Audit — 2026-08

Status: completed

Scope:

- `/analytics/alerts`
- Alertmanager and Prometheus alert-source selection
- Prometheus restart/readiness anomaly evidence
- committed `analytics.alerts` materialization
- Alerts and Anomalies table transport
- Analytics Overview alert snapshot
- Alerts & Anomalies report payload
- source normalization, deduplication, and code ownership

## Decisions

1. Alertmanager remains authoritative for routing and notification behavior.
2. The web page and report are committed-snapshot readers; they do not perform live provider reads.
3. Snapshot identity is limited to Cluster and Source. Severity, status, Namespace, search, tab, and pagination are presentation state.
4. Global page posture and recommendations use the full committed evidence set. Local filters only change record collections.
5. Restart and readiness anomaly queries execute independently and preserve successful evidence when the peer query fails.
6. Missing or partial evidence is Unknown or Limited Evidence, never synthetic zero, Normal, Stable, or Healthy.
7. Alerts and Anomalies own separate page and page-size parameters.
8. Fragment endpoints are HTMX-only transport surfaces and cannot be used as normal navigation destinations.

## Evidence corrections

### Active alerts

The Prometheus fallback query includes active `pending|firing` records. Alertmanager records prefer provider fingerprints. Prometheus records use canonical labels after removing HA replica labels, preventing replicas from producing duplicate cards.

Severity aliases are normalized before summary and filtering:

- `critical`, `fatal`, `error`, `page`, `P1` → Critical
- `warning`, `warn`, `P2` → Warning
- informational aliases and `P3/P4` → Info

### Pod restart anomalies

Restart counters are normalized by `namespace,pod,container` before Pod aggregation. The result is joined to Pods in `Pending|Running`, excluding terminal Pods and duplicate scrape inflation.

### Pod readiness anomalies

Readiness false series are normalized by `namespace,pod` and joined to active Pods. A terminal Pod cannot remain as a current readiness anomaly.

### Partial anomaly evidence

Restart and readiness query failures are isolated. The status contract records:

```text
available_queries
failed_queries
partial
connected
configured
```

When one family succeeds, its records remain available and the workspace shows a partial-evidence warning. When neither succeeds, anomaly evidence is unavailable while Alertmanager records may still remain usable.

## Runtime ownership

```text
app/kubernetes/analytics/alerts/
├── application.py   # materialization orchestration and committed presentation
├── anomalies.py     # independent anomaly collection
├── contracts.py     # typed selection and payload contracts
├── health.py        # source and page health
├── records.py       # normalization, deduplication, exact filtering
├── routes.py        # full page and HTMX transport
├── snapshots.py     # Analytics Overview projection
├── sources.py       # Alertmanager/Prometheus source policy
├── routing.py
├── silences.py
├── inhibition.py
├── ownership.py
├── readiness.py
└── signals.py
```

Raw PromQL is owned by:

```text
app/integrations/prometheus/query_profiles/alerts_v1.py
```

and registered under stable keys in `kubernetes_v1.py`.

## Presentation and transport

The canonical page remains `/analytics/alerts`. Alerts and Anomalies tables have independent state:

```text
alerts_page / alerts_per_page
anomalies_page / anomalies_per_page
```

Fragment endpoints require `HX-Request: true`. Direct requests redirect to the full page. Responses use:

```http
Cache-Control: no-store, max-age=0
Vary: HX-Request
HX-Push-Url: <canonical full-page URL>
```

Namespace filtering is exact. A Namespace such as `team-a` does not match `team-a-staging`.

## Report boundary

`app/reports/export/payloads/alerts.py` reads `analytics.alerts` with `source=auto`. Report rendering does not query Alertmanager or Prometheus. Missing committed evidence produces explicit Unknown/unavailable content and does not report zero active signals as Healthy.

## Analytics Overview boundary

The Overview snapshot includes:

```text
evidence_complete
anomaly_evidence_partial
status
tone
```

Stable is allowed only when alert-source evidence is connected, both anomaly signal families are complete, and no active signal requires review.

## Legacy and duplicate cleanup

- Provider normalization and filtering were removed from `sources.py` and assigned to `records.py`.
- Alertmanager and Prometheus duplicate records share one canonical deduplication path.
- The previous one-page parameter shared by Alerts and Anomalies was removed.
- Local filter results no longer overwrite global page posture or recommendation evidence.
- Incomplete anomaly evidence now creates a Warning recovery recommendation and cannot fall through to the Normal monitoring baseline.
- Report Namespace scope is preserved even when inventory options are stale; the report never broadens silently to all Namespaces.
- Report-time live provider calls were removed.
- No compatibility wrapper, route alias, architecture allowlist, or new code-health debt entry was added.

## Validation

The focused validation covers:

- severity/status normalization;
- Prometheus HA replica deduplication;
- exact Namespace filtering;
- independent anomaly query failure;
- active-Pod PromQL boundaries;
- independent table pagination;
- HTMX-only fragment transport;
- committed report ownership;
- incomplete-evidence Overview semantics;
- Python, Jinja, query-profile, import, architecture, source-hygiene, and obsolete-file checks.

Application startup and provider integration still require the KAORI Dev Container because the standalone audit environment does not include the full Flask dependency set or connected Alertmanager/Prometheus endpoints.

## Deployment

After deployment, rematerialize:

```text
analytics.alerts + cluster_id + source=auto
```

Then restart the Analytics worker and web process so the new query registry and presentation contracts are loaded. Restart the Reports worker because the report payload now reads the committed snapshot contract.
