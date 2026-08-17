# Analytics Metrics Source Readiness

## Purpose

Every Kubernetes Analytics workspace that depends on Metrics Source-backed metrics uses one canonical readiness component:

```text
app/templates/analytics/kubernetes/components/_metrics_source_status.html
```

The component owns both visual geometry and the data labels shown to operators. Pages must not rename the fields, substitute snapshot timestamps for provider checks, or rebuild the card locally.

## Canonical States

| State | Label | Tone | Meaning |
|---|---|---|---|
| `query_ready` | Query Ready | Normal | The selected source can execute Kubernetes Analytics queries. |
| `query_degraded` | Query Degraded | Warning | Queries remain eligible, but the latest runtime observation is degraded. |
| `unavailable` | Unavailable | Critical | The source cannot execute the required analytics query contract. |
| `not_configured` | Not Configured | Unknown | No eligible Metrics Source is configured and bound. |
| `waiting_for_cluster` | Waiting for Cluster | Disabled | There is no selected Kubernetes cluster to evaluate. |

Do not use page-specific labels such as `Metrics Source Connected`, `Metrics Source Query Ready`, `Source Healthy`, or `Connection Available` inside Analytics. The card title already identifies Metrics Source; the semantic badge therefore uses the concise canonical label.

## Canonical Data

Every card displays exactly:

1. `Metrics Source Status` title;
2. canonical semantic status;
3. one canonical readiness message;
4. `Response` from the latest persisted provider observation;
5. `Checked At` from `last_checked_at` on that same provider observation.

`Checked At` must never use materialization time, page render time, latest dataset time, or worker-attempt time. When no provider observation exists, display `Not Recorded`.

## Shared Python Presentation Contract

Analytics services normalize provider data through:

```text
app.analytics.kubernetes.common.presentation.present_metrics_source_status
```

The function preserves provider diagnostics while returning the canonical keys:

```text
schema_version
configured
connected
observation_degraded
state
status_label
tone
message
response_time_ms
response_time_display
last_checked_at
error
```

New Analytics domains must consume this contract rather than defining a new Metrics Source status dictionary.

## Placement

The standard controls/readiness layout is:

```text
Controls
Metrics Source Status | Latest Data Snapshot
Attention / Error Strip when required
```

Metrics Source readiness and committed dataset readiness are separate evidence boundaries. A Query Ready source does not prove that the committed dataset is current, and a current snapshot does not prove that the Metrics Source remains reachable.

## Alerts & Anomalies Exception

Alerts & Anomalies may resolve Alertmanager or Metrics Source dynamically. Its global readiness panel therefore remains `Alert Source Readiness`, not `Metrics Source Status`. When the resolved source is Metrics Source, it must still use the same provider observation semantics for response time and checked time, but the title reflects the multi-provider domain.

## Prohibited Patterns

- Passing a dataset timestamp as Metrics Source `Checked At`.
- Rendering latency as a page-specific pill while another page uses a metric cell.
- Recomputing connected/degraded labels in every template.
- Emitting CSS classes from Analytics services.
- Treating `Not Configured` as `Unavailable` or `Waiting for Cluster`.
- Hiding missing timestamps instead of showing `Not Recorded`.
