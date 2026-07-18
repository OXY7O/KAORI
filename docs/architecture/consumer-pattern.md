# Integration Consumer Pattern

A consumer is the only supported boundary between an asset domain and a provider integration.

## Simple consumer flow

```text
Analytics asks for data
        ↓
Consumer identifies the asset scope
        ↓
Resolver selects an eligible provider source
        ↓
Reader calls the selected provider
        ↓
Consumer returns canonical provider records
        ↓
Asset domain enriches and interprets the records
```

Analytics must not know the provider endpoint, credentials, TLS policy, compatibility profile, binding table, or HTTP client.

## Primary, secondary, and fallback in simple terms

These roles define preference, not simultaneous processing.

```text
Primary
→ first preferred source

Secondary
→ next source when it is healthier or the primary lacks a required capability

Fallback
→ last-resort source
```

Example:

```text
Cluster A requests alerts
        ↓
Primary supports Alerts API and is healthy
        ↓
Use Primary
```

If Primary is unhealthy:

```text
Cluster A requests alerts
        ↓
Primary is unhealthy
        ↓
Secondary is healthy
        ↓
Use Secondary
```

If the request is for silences and Primary lacks `silences_v2`:

```text
Cluster A requests silences
        ↓
Primary lacks Silences API
        ↓
Secondary has Silences API
        ↓
Use Secondary
```

The asset analytics code does not implement this selection.

## Resolver responsibilities

The resolver ranks bound sources using:

1. eligibility;
2. required capabilities;
3. runtime health;
4. readiness;
5. source role;
6. priority; and
7. deterministic tie-breaking.

It emits a decision trace explaining why each source was selected or skipped.

## Runtime fallback

Persisted state may become stale between validations. Therefore the consumer may try the next eligible source when the selected provider fails during the live request.

```text
Resolver selects Primary
        ↓
Live request fails
        ↓
Consumer tries Secondary
        ↓
Response records fallback_used and sanitized source errors
```

## Asset-domain boundary

Provider normalization remains generic. Kubernetes, Server, HCI, and Storage enrichment belongs to their own bounded contexts.

```text
Alertmanager consumer
→ canonical labels, annotations, state, timestamps, receiver, fingerprint

Kubernetes analytics
→ namespace, pod, workload, ownership, incident interpretation
```

## Required usage

New asset domains must consume providers through public consumer facades. Direct imports of provider models, repositories, credentials, clients, or validation services are prohibited outside the provider package and its approved compatibility layer.
