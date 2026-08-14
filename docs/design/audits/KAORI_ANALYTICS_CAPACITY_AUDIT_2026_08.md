# KAORI Analytics Capacity Audit — August 2026

## Decision

Capacity Analysis is retained as a cluster-level, worker-only scheduling workspace. The audit corrects the evidence boundary, removes repeated provider reads and legacy unscoped queries, separates filesystem reference data from schedulable capacity, and moves interpretation out of Jinja and the orchestration service.

## Findings Resolved

### Ready-worker wording did not match every query

The workspace stated that capacity was worker-only, but prior query variants did not consistently require the node to be Ready. The canonical Capacity query set now excludes `control-plane|master` nodes and intersects every scheduling signal with the Ready condition.

### Worker readiness cards mixed fleet boundaries

Worker count was combined with total-cluster Ready/NotReady numbers. Capacity now collects total worker count and Ready worker count from the same boundary, then derives NotReady workers from those two values. Total nodes and control-plane nodes remain context only.

### Provider signals were queried repeatedly

The former service composed multiple helpers that repeated CPU, memory, pod, filesystem, and utilization reads. `CapacityEvidenceCollector` now collects each required scheduling signal once per materialization. Optional filesystem reference signals are read once with `instant_query` only and cannot block scheduling readiness.

### Missing evidence could appear as zero or Healthy

Empty Prometheus results previously travelled through scalar helpers as zero. The new evidence objects retain `available` separately from `value`. Missing allocatable, request, limit, actual, peak, pod, or filesystem evidence renders Unknown/N/A and cannot produce a Healthy result.

### Requests, limits, current usage, and peak were conflated

Capacity domain logic now evaluates each signal independently. Request overcommit, limit overcommit, current pressure, and peak pressure have explicit status precedence and reasons. A missing peak is no longer replaced by current usage.

### Filesystem was treated as schedulable Kubernetes capacity

Node Filesystem is now marked `scheduling_resource=False`. It remains visible as an operational reference but is excluded from scheduling posture, lowest-headroom selection, governance findings, and Capacity recommendations. Storage Analysis owns filesystem remediation.

### Pod allocation duplicated the same signal

The duplicate “Pod Usage” representation was removed. The canonical pod profile is Pod Capacity, Current Pods, and Remaining Pod Slots.

### Presentation logic was duplicated

Capacity interpretation now has explicit ownership:

```text
evidence.py      provider evidence and availability
domain.py        calculations, statuses, risk, governance
service.py       orchestration and recommendations
presentation.py  display normalization and bottleneck selection
Jinja            rendering only
```

The shared `app.analytics.kubernetes.common.presentation` package no longer contains a Capacity-specific presenter.

### Filters lost the active tab

The Capacity filter now participates in the canonical `data-analytics-preserve-tab` contract. `tab` remains in the browser query string while being excluded from the committed snapshot fingerprint.

### Legacy query definitions remained registered

Unused unscoped Capacity query definitions were removed. Only the Ready-worker query family remains registered for Capacity materialization.

## UI Review

- Progress fills use Bright Violet consistently.
- Semantic status remains in compact labels and guidance, not progress colors.
- Missing evidence suppresses progress and displays N/A.
- Primary evidence uses bright surfaces.
- Review guidance uses shared darker Analytics guidance surfaces.
- Capacity remains cluster-level; node drill-down remains in Resource Utilization.
- Node Filesystem is labelled as an operational reference, not allocatable storage.

## Deployment Note

The PromQL and interpretation contract changed. Existing committed Capacity snapshots can retain the old boundary until replaced. After deployment, rematerialize configured `analytics.capacity` time-range variants or allow the scheduled Analytics worker to refresh them before validating production values.

## Validation Scope

The patch is validated through focused Capacity contracts, standalone presenter tests, Analytics static contracts, PromQL profile validation, Python/Jinja syntax checks, internal import verification, code-health and source-hygiene gates, obsolete-file checks, and patch reproduction against the parent commit.

## Validation Result

- 46 focused Capacity, materialization, presentation, and report-publication contracts passed.
- 185 of 189 Analytics static contracts passed. The four remaining failures are unchanged baseline items in Storage, Workload pagination, and Intelligence presentation; none reference Capacity files.
- Capacity domain tests cover non-finite Prometheus values, request-overcommit precedence, incomplete peak evidence, aggregate posture, filesystem exclusion, and separate worker/full-cluster readiness.
- Capacity templates parse successfully with Jinja.
- Python syntax, internal import-symbol validation, source hygiene, obsolete-file checks, and `git diff --check` pass.
- The Capacity page modules no longer appear in the code-health failure set. Global code-health and dependency-cycle verifiers still report the same unrelated baseline findings present on the parent commit.
- The static Analytics PDF publication contract passes. The Flask-dependent Capacity PDF template test cannot be collected in the audit runtime because the `Flask` package is not installed. No Capacity PDF layout source is changed by this patch.

## Cross-Surface Compatibility

The committed payload retains full-cluster `ready_nodes` and `not_ready_nodes` for the existing Capacity report while adding the canonical Ready-worker fields used by the page. Dashboard projection now respects `evidence_available=False` and returns unavailable values instead of formatting missing evidence as `0 / 0`. Analytics Overview continues to consume exact time-range Capacity snapshots and receives `None` for unavailable headroom.
