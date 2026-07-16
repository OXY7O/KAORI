# Integration compatibility and readiness

KAORI treats reachability, compatibility, and readiness as separate states. A successful TCP/TLS connection does not authorize an integration for runtime use.

## Validation lifecycle

1. Save configuration.
2. Mark the integration `validation_required`.
3. Detect product identity and version.
4. Match a version-controlled compatibility profile.
5. Validate required APIs and capabilities.
6. Select the query/API profile.
7. Persist validation evidence and readiness.
8. Allow consumers to use only integrations that are not explicitly blocked.

Unknown and unsupported versions fail closed. Missing optional capabilities may be represented as degraded; missing required capabilities are blocked.

## Initial KAORI profiles

| Product | Version constraint | Profile | Behavior |
|---|---:|---|---|
| Kubernetes | `>=1.20,<1.24` | `kubernetes-legacy-v1` | Compatible with warnings; validate each feature and API resource independently. |
| Kubernetes | `>=1.24,<1.30` | `kubernetes-standard-v1` | Supported initial cluster profile. |
| Prometheus | `>=2.0,<3.0` | `prometheus-http-api-v1` | Stable `/api/v1` HTTP API and KAORI PromQL registry. |
| Alertmanager | `>=0.25,<1.0` | `alertmanager-api-v2` | API v2 only. |

These constraints are KAORI support policy, not a claim about upstream maintenance status. Extend them only after automated API and query validation is added for the new range.

## Current supplied estate

- Kubernetes `v1.20.15`: legacy profile, warning state.
- Kubernetes `v1.26.11`, `v1.29.4`, `v1.29.5`: standard profile.
- Prometheus `2.43.0`: supported profile.
- Prometheus `0.39.2`: blocked because it does not match the supported Prometheus 2.x profile.
- Alertmanager `0.25.0`, `0.33.1`: evaluated against API v2 and must still pass status, alerts, and silences probes.

## Deprecation handling

Compatibility profiles live in `app/integrations/compatibility.py` and are version controlled. Deprecated syntax, removed APIs, changed response schemas, and PromQL/metric-label changes must create a new profile rather than silently changing an existing one.

For Kubernetes, readiness is feature-specific. A legacy cluster may remain usable for inventory while a mutation workflow is blocked because a required API resource or verb is unavailable.

For Prometheus, future query packs must declare required metrics, labels, result type, and replacement query. For Alertmanager, KAORI never falls back to API v1; upstream API v1 was deprecated and later removed.

## Deployment

Run the database migration before starting the updated application:

```bash
flask db upgrade
```

Existing configurations have no validation evidence after migration. Open the integration configuration and run connection validation before treating them as ready.
