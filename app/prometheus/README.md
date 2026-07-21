# Prometheus Domain Boundary

`app/prometheus` owns KAORI's Prometheus registration workflow, instance
workspace, scope binding policy, source resolution, presentation, audit, and
HTTP routes.

The provider implementation is exclusively owned by
`app/integrations/prometheus/`. Transport, query profiles, capability
declarations, validation, evidence collection, compatibility profiles, and the
runtime adapter must not be added here.

Domain services call the Integration Registry for provider operations.
Persistence uses `PrometheusInstance`, `IntegrationInstance`, and
`IntegrationBinding` only. There are no Python import facades for the retired
provider package; old URL bookmarks are handled centrally by
canonical integration routes only; retired bookmark redirects are removed.
