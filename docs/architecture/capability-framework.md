# Capability Framework

## Principle

KAORI consumers depend on capabilities, not provider version strings.

Avoid:

```python
if version >= "0.33":
    ...
```

Prefer:

```python
if "silences_v2" in capabilities:
    ...
```

## Capability layers

### Provider API capability

Verified through provider endpoints, for example:

```text
status_v2
alerts_v2
silences_v2
```

### Observed payload capability

Discovered from actual payload metadata, for example:

```text
fingerprint
severity_label
receiver_metadata
summary_annotation
runbook_url
```

A payload capability may be `not observed` when no representative data exists. This is different from confirmed unsupported behavior.

### Module requirement

Each KAORI feature declares required and optional capabilities.

Example:

```text
Alert Inventory
Required: alerts_v2, alert_labels, alertname_label
Optional: fingerprint, severity_label
```

## Feature readiness

```text
Ready
→ all required and optional capabilities are available

Degraded
→ required capabilities are available, optional capabilities are missing or not observed

Unavailable
→ at least one required capability is unavailable
```

## Metric compatibility relationship

For Prometheus, capability validation primarily checks metric and PromQL availability.

For Alertmanager, capability validation checks API endpoints and alert/silence payload metadata.

The shared pattern is identical:

```text
Provider evidence
        ↓
Canonical capabilities
        ↓
Module requirements
        ↓
Feature readiness
```

## Registry rule

Capability keys must be canonical, stable, documented, and provider-domain owned. UI labels may change; capability keys must not change casually because resolvers and consumers depend on them.

## Complete contract validation and remediation

A capability is ready only when its complete consumer contract passes. For metrics integrations this includes the query API, metric name, required label schema, identity correlation, and required history. A fallback query based on `instance="IP:port"` must be reported as degraded or misconfigured when the canonical consumer contract requires a Kubernetes node identity.

Every capability status other than `available` must provide impact, observed evidence, source owner, recommended source-side change, expected signal, and—when useful—a validation query. Version is advisory; observed capability is authoritative, including when KAORI connects through Thanos Query and cannot observe the backend Prometheus version.
