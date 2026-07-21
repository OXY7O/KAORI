# Alertmanager Domain Boundary

`app/alertmanager` owns KAORI's Alertmanager registration workflow, instance
workspace, scope binding policy, source resolution, presentation, audit, and
HTTP routes.

The provider implementation is exclusively owned by
`app/integrations/alertmanager/`. Transport, normalizers, compatibility
profiles, capability declarations, validation, probes, readers, and the runtime
adapter must not be added here.

Domain services call the Integration Registry for provider operations.
Persistence uses `AlertmanagerInstance`, `IntegrationInstance`, and
`IntegrationBinding` only. There are no Python import facades for the retired
provider package; old URL bookmarks are handled centrally by
canonical integration routes only; retired bookmark redirects are removed.
