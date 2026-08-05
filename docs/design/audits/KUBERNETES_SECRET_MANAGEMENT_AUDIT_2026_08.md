# KAORI Kubernetes Secret Management Audit — August 2026

## Scope

Secret Management landing, create, replace, delete, protected reveal, TLS operations, Activity Audit, and operational toast integration.

## Canonical decisions

- Landing counters read only the latest committed Configuration Inventory generation.
- Create and replace use one service-owned server-side dry-run immediately before one mutation.
- Delete authorization validation issues a signed stateless receipt bound to user, cluster, namespace, Secret name, resourceVersion, and a ten-minute lifetime.
- Browser changes invalidate the delete receipt and final action.
- Secret values are never persisted in Inventory, notifications, Activity Audit metadata, or toast payloads.
- Protected Reveal remains approval-gated, step-up authenticated, one-time, and blocked-key aware.
- Operational outcomes use the shared KAORI operational toast and Activity Audit pipeline.

## Removed compatibility debt

- Route-level `validate_then_apply` wrapper for Secret create and replace.
- Session-bound Secret deletion receipt.
- Uploaded-file rewind helper that existed only for duplicate route/service validation.
- Legacy session-oriented delete workflow test.

## Runtime verification still required

Execute live create, replace, delete, reveal, and TLS workflows against a disposable namespace with representative RBAC policies.
