# Permission Registry Review

## 1. Review result

The current registry contains **54 permission keys**. Static review of Python route guards, aggregate guards, runtime `has_permission()` checks, navigation visibility, and welcome shortcut declarations found no application permission reference that is missing from `DEFAULT_PERMISSIONS`.

This means the registry is complete for the current code surface. It does not mean every registered key is an active independent authorization boundary.

## 2. Permission lifecycle classifications

KAORI currently stores only key, module, action, and description. Until explicit lifecycle metadata exists, the following classifications must be maintained in documentation.

### 2.1 Active authorization keys

Most registry keys are active server-side contracts enforced by `permission_required()`, `any_permission_required()`, or an equivalent service policy. Examples include:

- `clusters.view`, `clusters.manage`, and `clusters.sync`;
- `users.view`, `users.manage`, and user lifecycle actions;
- `roles.view` and `roles.manage`;
- ConfigMap, Secret, TLS rotation, report, audit, and integration actions.

UI visibility must follow these keys, but server-side enforcement remains authoritative.

### 2.2 Authenticated baseline key

`settings.view` remains assigned to every protected default role, while personal General Settings remains available to authenticated users by product design. It is therefore a baseline capability rather than an independent deny boundary and must not be presented as a reliable way to remove self-service settings access from a custom role. Settings final recheck will resolve whether this key should be formalized or retired.

`welcome.view` is no longer part of the registry. Welcome is an authenticated landing route, so retaining a permission that did not guard the route created a false authorization contract. Migration `20260810_retire_welcome_view` removes the key and its historical role assignments.

### 2.3 Reserved key

`system.manage` is registered and included in Admin, but no current system-management mutation route uses it.

It must be treated as **reserved**, not as proof that a user can perform an existing system-management operation. Before a future feature adopts this key, its exact scope and sensitive-operation exclusions must be reviewed.

### 2.4 Retired TLS mutation keys

The retired `tls_certificates.update` and `tls_certificates.bulk_update` permissions are removed. Existing role assignments are migrated to `kubernetes_secrets.rotate_tls` and `kubernetes_secrets.bulk_rotate_tls`.

TLS Governance now owns only read and synchronization capabilities. Current UI, navigation, and rotation handoffs use Kubernetes Operations Secret permissions:

- `kubernetes_secrets.rotate_tls`;
- `kubernetes_secrets.bulk_rotate_tls`.

Migration `20260805_secret_ops_v2` transfers existing role assignments to the canonical Secret permissions before deleting the retired registry rows and their old role-permission links. No compatibility aliases remain active.

## 3. Admin aggregation review

The Admin default role currently receives every registered permission except `kubernetes_secrets.reveal`.

This is acceptable for the current registry, but it creates a forward-security obligation: every newly registered permission automatically enters Admin unless explicitly excluded. New high-sensitivity actions must be classified before release and must not rely on the comprehension alone.

Recommended future structure:

```text
ADMIN_EXCLUDED_PERMISSIONS = {
  kubernetes_secrets.reveal,
  <future high-sensitivity keys>
}
```

The current implementation already applies the equivalent exclusion for direct Secret reveal.

## 4. Required lifecycle improvement

Extend permission metadata in a future migration with fields or code-owned metadata equivalent to:

- `lifecycle_status`: `active`, `baseline`, `reserved`, or `deprecated`;
- `replacement_key`: optional canonical replacement;
- `sensitivity`: `normal`, `privileged`, or `protected`;
- `introduced_version`;
- `deprecated_version`;
- operator-facing migration note.

Permission Catalog should then expose lifecycle status without allowing administrators to rename or mutate registry contracts.

## 5. Static verification recommendation

CI should fail when:

- a route, service, template, or shortcut references an unregistered key;
- a default role references an unregistered key;
- a deprecated key is introduced in new code;
- a protected permission enters Admin without an explicit review decision.

The repository now includes initial RBAC service regression tests. A registry-reference scanner and endpoint authorization matrix remain the next automated controls.
