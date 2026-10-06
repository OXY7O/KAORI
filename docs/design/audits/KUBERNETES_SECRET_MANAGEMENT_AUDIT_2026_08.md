# KAORI Kubernetes Secret Management Audit — August 2026

## Scope

Secret Management landing, create, replace, delete, Protected Reveal, TLS operations, Activity Audit, operational toast, and Notification Deck delivery.

## Canonical decisions

- Landing counters read only the latest committed Configuration Inventory generation.
- Create and replace never trust the browser validation state. A final mutation performs one fresh Kubernetes server-side dry-run followed by one provider mutation through the shared `validate_then_apply` operation boundary.
- Uploaded streams are rewound only between the fresh dry-run and provider mutation; Secret values are scrubbed immediately after each provider call.
- Delete authorization validation issues a signed stateless receipt bound to user, cluster, namespace, Secret name, `resourceVersion`, and a ten-minute lifetime.
- Browser target or confirmation changes invalidate the delete receipt and disable the final action.
- Secret values are never persisted in Inventory, Notification Deck metadata, Activity Audit metadata, or toast payloads.
- Protected Reveal remains approval-gated, step-up authenticated, one-time, and blocked-key aware.
- Create/replace success uses toast plus Activity Audit without Notification Deck noise; warning/failure is visible in the Deck.
- Delete and security-sensitive reveal lifecycle events are persistent in the Notification Deck.
- One-time reveal completion is audit-only and never stores the revealed value.

## Removed compatibility debt

- Monolithic Secret route module was split into canonical CRUD, reveal, and TLS route owners.
- Session-bound Secret deletion receipt and GET-session restoration were removed.
- Historical Inventory rows are no longer used for landing or impact counts.
- Retired TLS mutation permission aliases are migrated to canonical Kubernetes Secret permissions.
- Legacy session-oriented delete workflow tests were replaced with signed-receipt and mutation-boundary tests.

## Runtime verification still required

Execute live create, replace, delete, reveal, and TLS workflows against a disposable namespace with representative RBAC policies. Confirm operational toast behavior, Notification Deck visibility, Activity Audit persistence, resource-version conflict handling, and value non-disclosure.
