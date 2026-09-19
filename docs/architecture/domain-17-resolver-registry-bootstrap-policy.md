# Domain 17 — Resolver Registry Bootstrap & Deployment Policy Wiring

## Purpose
Create one deterministic resolver registry configuration for web and worker processes, and persist cluster/action deployment policy separately from runbook publication.

## Safety contract
- Unknown enabled actions fail startup.
- Kubernetes action enablement requires an explicit namespace allowlist.
- The registry fingerprint is deterministic and must match the fingerprint recorded in an active cluster policy before dispatch is enabled; the resolver worker enforces this before lease acquisition.
- Policy defaults to `disabled`; migration does not auto-enable any resolver.
- Registry initialization occurs before Celery initialization so workers inherit the same application configuration.

## Configuration
- `RESOLVER_ENABLED_ACTIONS`: comma-separated action allowlist.
- `RESOLVER_KUBERNETES_ALLOWED_NAMESPACES`: explicit comma-separated namespace allowlist.
- Empty action configuration creates an empty registry and keeps remediation disabled.

## Deployment
1. Apply migration.
2. Configure actions and namespaces identically for web and resolver workers.
3. Start web and workers; capture `RESOLVER_REGISTRY_FINGERPRINT`.
4. Create a disabled cluster/action policy with that fingerprint.
5. Validate readiness, then activate policy explicitly.

## Validation
Run focused functional and contract tests, architecture validation, and compare registry fingerprints across all process types.

## Rollback
Disable all resolver deployment policies, drain resolver queues, stop resolver workers, downgrade to `20260723_candidate_review`, and remove resolver environment configuration.
