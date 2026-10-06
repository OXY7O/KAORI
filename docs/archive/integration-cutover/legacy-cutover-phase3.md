# Legacy Cutover Phase 3

Prometheus now exposes an instance-centric entry point at `/integrations/prometheus/instances` while existing cluster routes remain compatibility endpoints. Canonical `IntegrationBinding` records are the only binding records created by the new Prometheus mapping workflow.

The instance list is ordered by registration time (`created_at`, then `id`) and presents display-ready readiness and last-checked values. A Prometheus or Thanos runtime may be mapped to multiple Kubernetes assets without duplicating provider connection records.

Destructive removal of the legacy provider tables is intentionally deferred until the repository-wide guard remains clean across application and test fixtures.
