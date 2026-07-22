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
`IntegrationBinding` only. No alternate Python import path remains for the retired provider package.
Canonical integration routes are the only registered URL owners; replaced bookmark
redirects are removed.

## Workspace composition

Registration and configuration uses the shared Info Flow component for ordered
operator guidance. Validation uses the shared Context Guidance Card only for
secondary remediation context; provider execution remains owned by the
Integration Registry adapter.
