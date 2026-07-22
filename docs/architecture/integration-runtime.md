# Integration Runtime Framework

## Purpose

The Integration Runtime Framework is the shared operational foundation for every external provider integrated with KAORI. It separates stable configuration from changing runtime observations so Prometheus, Alertmanager, Harbor, Vault, Velero, GitHub, MinIO, Argo CD, Ansible, and future providers follow the same lifecycle and UI vocabulary.

```text
Provider configuration
        ↓
Provider runtime adapter
        ↓
Validation and capability discovery
        ↓
Shared RuntimeState
        ↓
Health, diagnostics, snapshot, and presentation
        ↓
Provider consumer
```

## Configuration versus runtime

Configuration is the operator-defined connection contract and normally changes infrequently:

```text
endpoint
authentication mode
credential reference
TLS policy
timeout
enabled state
```

Runtime is the latest observed operational condition and may change continuously:

```text
reachable or unreachable
authentication success or failure
latency
detected version
available capabilities
health score
last success
last failure
```

Changing runtime state must never silently rewrite operator configuration.

## Shared runtime contract

A provider adapter returns a provider-neutral runtime state containing:

- provider and instance identity;
- observation time;
- readiness;
- health status and score;
- diagnostics;
- capability snapshot;
- compatibility profile;
- latency;
- last success and failure; and
- a sanitized operator message.

Shared UI components and future integration dashboards consume this runtime state. They must not inspect provider-specific models or HTTP clients.

## Readiness versus health

Readiness answers:

> Is this configuration compatible and permitted for consumer use?

Health answers:

> What is the latest observed runtime condition?

A provider may therefore be:

```text
Readiness: Ready
Health: Unhealthy
```

This means the configuration is valid, but the provider is currently unavailable.

## Runtime refresh flow

```text
Operator or scheduler requests refresh
        ↓
Shared refresh orchestrator calls provider adapter
        ↓
Adapter runs provider-specific validation
        ↓
Adapter discovers capabilities and compatibility
        ↓
Shared health scoring evaluates factors
        ↓
RuntimeState is returned
        ↓
UI partial, audit event, and future history storage are updated
```

Manual HTMX refresh and scheduled background refresh must use the same adapter and orchestration path.

## Health scoring

Health is calculated from weighted factors rather than a single badge. Typical factors include:

- connectivity;
- TLS;
- authentication;
- provider API;
- readiness;
- capability discovery;
- latency; and
- recent failures.

A critical failed factor may force an unhealthy result even when non-critical factors are successful. Provider-specific weights may vary, but the output contract remains `healthy`, `degraded`, or `unhealthy` with a score from 0 to 100.

## Diagnostics

Each diagnostic step contains:

```text
name
category
status
duration
severity
message
recommendation
```

Diagnostic messages must be actionable and sanitized. They must never expose credentials, authorization headers, private key material, raw query strings, or unfiltered provider responses.

## Snapshot and history direction

A runtime snapshot represents the provider state at an observation point:

```text
version
compatibility profile
capability profile
capabilities
observed metadata
health
observed at
```

The current framework defines the canonical snapshot contract. Historical persistence and scheduled monitoring are separate phases and must reuse this contract rather than introduce provider-specific history tables or payloads.

## Provider boundary

The shared framework owns contracts, scoring, refresh orchestration, and presentation vocabulary. Provider packages own:

- endpoint and credential translation;
- API calls;
- version discovery;
- capability probing;
- compatibility mapping;
- provider-specific diagnostics; and
- conversion into the shared runtime contract.

Provider-specific logic must not be added to `app/integrations/runtime/`.

## Current implementation

```text
app/integrations/runtime/
├── contracts.py
├── scoring.py
├── monitoring.py
├── repository.py
├── presentation.py
└── tasks.py                 # Beat dispatcher only

app/integrations/validation/
├── state.py                 # Redis distributed locks and transient polling metadata
├── tasks.py                 # full, binding, and lightweight runtime jobs
└── web.py                   # canonical job enqueue and polling boundary

app/jobs/
├── service.py               # PostgreSQL lifecycle, deduplication, quotas, subscribers
├── dispatcher.py            # provider-neutral future analytics dispatch
├── execution.py             # cooperative progress and cancellation
├── query_planning.py        # large query chunk/sample guardrails
└── tasks.py                 # stale-job recovery

app/integrations/runtime/kubernetes_adapter.py
app/prometheus/runtime_adapter.py
app/alertmanager/runtime_adapter.py
```

Kubernetes, Prometheus, and Alertmanager implement the provider-neutral runtime contract. Provider-specific probes remain inside their owning domains.

## Runtime evidence and scheduled monitoring

A refresh is not only a UI action. Manual Runtime Refresh and scheduled monitoring both append a runtime observation, but scheduled monitoring must remain lightweight. Celery Beat performs no provider I/O; it fans out one independent task per provider instance to the dedicated `integration-runtime` queue. Prometheus and Alertmanager scheduled jobs verify reachability, identity, latency, and current health without rebuilding the full capability catalog. Full Validation remains a separate worker operation that rebuilds compatibility, capability, query/API contract, retention, and readiness evidence. Kubernetes runtime health uses a lightweight API version and reachability probe that preserves the latest capability evidence. Full Validation is the only workflow that rebuilds served-API discovery, compatibility, adapter selection, and capability evidence.

Manual actions return after enqueueing and poll through HTMX. PostgreSQL provides the canonical active-job registry and multi-user deduplication. Redis adds fast provider locks and atomically blocks Full Validation from overlapping Runtime Refresh for the same instance. Provider credentials and raw validation payloads are never copied into job payloads, task metadata, or runtime observations.

The runtime repository applies rolling retention after each append. It keeps the
latest **100 observations per provider and provider-native instance ID**, then
removes older rows in the same database transaction. Retained observations are
not edited in place.

## Runtime history user interface

The shared runtime history is rolling operational evidence, not an editable event
log. Provider detail pages show the latest observations in reverse chronological
order and default to 5 rows with 5, 10, 25, and 50 page-size options. The footer
keeps the summary and page-size selector together on the left and navigation on
the right.

The presentation layer compares each observation with the immediately older
observation to derive display-only markers:

```text
Healthy after Degraded/Unhealthy → Recovered
Healthy to Degraded             → Degraded
Any state to Unhealthy          → Became unhealthy
Unhealthy to Degraded           → Improving
Capability added or removed     → Capability drift
```

These markers do not modify persisted observations and must not influence source
selection. Resolver and consumer decisions continue to use canonical current
runtime state. HTMX refresh of the runtime panel also refreshes the first history
page out-of-band so the newly persisted observation becomes visible without a
full page reload.

## Shared integrations overview

The global Integrations Overview may aggregate the latest persisted runtime observation across providers. It must not duplicate provider configuration forms or implement provider-specific validation. Its responsibilities are limited to health/readiness posture, capability-attention counts, observation freshness, filtering, and navigation to the owning provider page.

A target without an observation is shown as `Not Observed`; it must not be inferred as healthy merely because configuration exists. Provider detail pages remain the authoritative location for remediation instructions and evidence.

## Presentation boundary

Runtime templates consume presentation-ready view models. They must not format
raw datetimes, derive user timezone output, pluralize counters, or humanize
canonical status keys. These transformations belong to the Python presentation
layer so full-page and HTMX responses use the same representation.

Required pattern:

```text
Persisted UTC datetime
        ↓
Presentation layer applies the authenticated user's timezone and locale
        ↓
`observed_at_display`
        ↓
Template renders the supplied string
```

A runtime row may retain the raw value for sorting or internal logic, but the
Jinja template must render `*_display` fields. Provider adapters and persistence
remain timezone-neutral; user preferences affect presentation only.


## Template normalization rule

Integration Runtime templates render presentation-ready values only. Datetime conversion, canonical-key labels, counters, units, latency strings, and health-score strings are produced in Python. Jinja templates must not call `strftime`, timezone filters, `replace(...).title()`, or construct unit/plural display strings for runtime data. When a touched template still performs such formatting, normalize it in the same change.
