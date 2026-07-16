# Alertmanager Integration

Alertmanager uses two readable contracts:

- Endpoint/API profile: `alertmanager-api-v2-legacy` or `alertmanager-api-v2-current`
- Capability profile: `alert-management-v1`

Version detection is automatic. KAORI validates `/api/v2/status`, `/api/v2/alerts`, and `/api/v2/silences`. API v1 is never used.

The endpoint profile represents runtime/API compatibility. The capability profile represents the alert-management behavior required by Alerts & Anomalies, Alert Intelligence, silence operations, and routing posture.
