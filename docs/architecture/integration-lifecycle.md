# Integration Lifecycle Standard

Every KAORI integration must follow the same lifecycle.

```text
Registration
    ↓
Configuration
    ↓
Validation
    ↓
Capability Discovery
    ↓
Compatibility Mapping
    ↓
Runtime Snapshot
    ↓
Health Scoring
    ↓
Diagnostics
    ↓
Consumer Availability
    ↓
Scheduled Monitoring
    ↓
Historical Tracking
```

## 1. Registration

An external provider deployment is registered once as a reusable integration instance. Registration identifies the deployment; it does not imply that every asset domain may consume it.

## 2. Configuration

The operator supplies endpoint, authentication, TLS, timeout, and lifecycle settings. Secrets must be protected and omitted from presentation and audit metadata.

## 3. Validation

Validation proves that the configured endpoint can be reached and used. Validation should be step-based so operators can identify whether failure occurs at DNS, TLS, authentication, API, or compatibility.

## 4. Capability discovery

KAORI records what the provider actually exposes. Consumers must depend on capabilities, not hard-coded version comparisons.

## 5. Compatibility mapping

The detected version and provider behavior are mapped to a named compatibility profile. Profiles document supported APIs and known limitations.

## 6. Runtime snapshot

The latest observed version, capabilities, metadata, readiness, and health are represented as a canonical runtime snapshot.

## 7. Health scoring

Shared scoring converts diagnostic factors into a stable status and score. Readiness and health remain separate.

## 8. Diagnostics

Failures are represented as actionable diagnostic steps with sanitized messages and recommendations.

## 9. Consumer availability

A consumer may use the integration only when the required binding, readiness, health policy, and capabilities are satisfied. Consumers must not directly manage provider configuration or connection details.

## 10. Scheduled monitoring

Background monitoring reuses the same runtime adapter used by manual validation. Scheduled jobs must not contain duplicate validation logic.

## 11. Historical tracking

Future history storage records runtime transitions, capability changes, recovery, degradation, and validation evidence. Activity Audit remains the administrative audit source; runtime history records operational observations.

## Lifecycle rule

No integration page should invent a separate lifecycle. Provider differences belong in adapters; lifecycle and presentation remain consistent across KAORI.
