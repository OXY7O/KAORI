# KAORI Analytics Forecast Runtime Audit — 2026-08

Status: Completed
Scope: Kubernetes Analytics → Resource Forecast

## Audit Objective

Verify that Resource Forecast uses the documented KAORI evidence boundary, does not present missing or weak evidence as healthy, does not create unnecessary materialization variants, and has no active legacy route or monolithic ownership left in the page runtime.

## Findings and Resolution

### Ready-worker numerator and denominator mismatch

CPU and memory demand previously included workload activity outside the worker boundary while capacity excluded control-plane nodes. Pod demand also did not use the same active-Pod and Ready-worker contract.

Resolution:

- workload series join Pod-to-node identity;
- only Ready worker nodes are retained;
- `control-plane|master` roles are excluded;
- Pods use `Pending|Running`;
- duplicate series are normalized before aggregation.

### Storage denominator ambiguity

Forecast copy and queries could be interpreted as requested claim capacity. Storage Analysis already standardized pressure against observed mounted-volume capacity.

Resolution:

- usage and capacity come from kubelet volume statistics;
- duplicate PVC samples use `max by(namespace,persistentvolumeclaim)`;
- UI and report wording use Observed Volume Capacity.

### Endpoint-only risk classification

A seasonal forecast could cross a threshold before the final day and return below it at the endpoint. Endpoint-only classification therefore understated exposure.

Resolution:

- status, highest projection, and report exposure use peak projected percentage inside the horizon;
- endpoint remains visible separately.

### Unbounded linear ETA

Threshold ETA previously derived from slope and wall-clock time, which could report a crossing beyond the selected horizon as though it belonged to that horizon.

Resolution:

- walk actual projected points;
- anchor on the latest historical timestamp;
- return a crossing only inside the selected horizon;
- otherwise return `Beyond <horizon>d horizon`.

### Weak evidence shown as healthy

A normal endpoint with low historical quality could produce a healthy overall posture.

Resolution:

- High/Medium quality is planning-ready;
- Low quality is Limited Evidence;
- aggregate Within Capacity requires complete, planning-ready evidence for all resources.

### Misaligned combined chart

Series with different dates could be plotted against labels from another resource.

Resolution:

- build one union timestamp axis;
- map each historical and forecast series to that axis;
- retain missing points as null;
- use a dynamic y-axis ceiling.

### Snapshot proliferation

Forecast horizon, model, and tab are local projection state but were at risk of becoming materialization dimensions.

Resolution:

- committed identity is Cluster + History Window + optional Namespace;
- Horizon, Model, and Tab are projected locally from committed history;
- the longest supported history requirement is 90 days.

### Unused fragment route

`/analytics/kubernetes/forecast/section` no longer had a consumer but remained registered.

Resolution:

- remove the route, endpoint import, and navigation reference;
- retain only the canonical full-page route.

### Monolithic service and duplicated ownership

The Forecast service mixed query orchestration, model calculation, presentation, snapshot adaptation, and chart shaping.

Resolution:

- split contracts, calculation, resource, presentation, service, and route ownership;
- reduce every Forecast runtime module to no more than 800 lines;
- remove resolved service module/function debt entries.

### Inline JSON script debt

The chart payload used an inline `<script type="application/json">` and remained in the inline-code debt baseline.

Resolution:

- move payload into a non-executable `<template data-kaori-json-payload>`;
- update chart runtime parsing;
- remove the resolved debt entry.

### Report threshold drift

The page domain used 75%/90%, while parts of the Forecast PDF still described and drew 70%/85%.

Resolution:

- import canonical Forecast threshold constants;
- update methodology, chart guides, exposure register, and source evidence;
- use peak projection for report exposure status;
- read collection time from the committed snapshot.

## Canonical Runtime Flow

```text
Forecast page request
    ↓
Resolve analytics.forecast snapshot
    ↓
Identity: cluster_id + history_window + optional namespace
    ↓
Forecast worker reads Ready-worker/PVC history once
    ↓
Committed historical evidence
    ↓
Presentation re-projects selected model + horizon locally
    ↓
Peak risk, bounded ETA, posture, chart, recommendations
```

## Deployment Requirement

After deployment, refresh `analytics.forecast` for configured Cluster/History Window variants. Namespace-specific snapshots are generated on demand and deduplicated by the canonical snapshot identity. Existing snapshots may still contain the previous all-node demand boundary or endpoint-only status until replaced.

## Regression Guardrails

The audit adds contracts for:

- module ownership and line limits;
- snapshot dimension separation;
- Ready-worker PromQL and duplicate normalization;
- 90-day history declaration;
- peak-based status;
- projected-point ETA;
- Limited Evidence posture;
- timestamp-aligned charts;
- legacy route removal;
- report threshold and peak-projection parity.

## Post-audit Runtime Correction — 2026-08-06

A production-like request to `/analytics/forecast` exposed an uninitialized local variable in the non-actionable recommendation path. The ETA recommendation refactor moved trend-link construction into `_build_forecast_eta_recommendation()`, while the two baseline fallback cards still referenced `trend_href` from the former function-local block.

Resolution:

- initialize the canonical Trend review URL once at the start of `build_forecast_actionable_recommendations()`;
- continue using the same scoped URL contract for both baseline fallback recommendations;
- add a runtime regression test that executes the empty/non-actionable payload path and verifies both fallback cards, their Trend URL, namespace preservation, and non-actionable state.

This correction does not alter Forecast evidence, thresholds, materialization identity, or recommendation priority semantics.
