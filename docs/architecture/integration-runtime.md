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
├── refresh.py
└── presentation.py

app/alertmanager/runtime_adapter.py
```

Alertmanager is the first adapter. Prometheus should become the second adapter after the shared contract is validated in production use.

## Runtime evidence and scheduled monitoring

A refresh is not only a UI action. Both manual HTMX refresh and Celery Beat
must execute the same adapter orchestration and append an immutable runtime
observation. This provides validation history, health trend input, capability
change evidence, and a stable data source for the shared Integrations dashboard.
Provider credentials and configuration are never copied into the observation.
