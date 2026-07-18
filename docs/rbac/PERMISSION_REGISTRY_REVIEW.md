# Permission Registry Review

## 1. Review result

The current registry contains **45 permission keys**. Static review of Python route guards, aggregate guards, runtime `has_permission()` checks, navigation visibility, and welcome shortcut declarations found no application permission reference that is missing from `DEFAULT_PERMISSIONS`.

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

### 2.2 Authenticated baseline keys

`welcome.view` and `settings.view` are assigned to every protected default role, but the Welcome workspace and personal General Settings remain available to authenticated users by product design.

Consequences:

- these keys are not currently strict route-level deny boundaries;
- they should not be presented as a reliable way to remove Welcome or self-service settings access from a custom role;
- a future cleanup should either formalize them as authenticated baseline capabilities or remove them through an explicit compatibility migration.

### 2.3 Reserved key

`system.manage` is registered and included in Admin, but no current system-management mutation route uses it.

It must be treated as **reserved**, not as proof that a user can perform an existing system-management operation. Before a future feature adopts this key, its exact scope and sensitive-operation exclusions must be reviewed.

### 2.4 Legacy compatibility keys

`tls_certificates.update` and `tls_certificates.bulk_update` remain in the registry for compatibility with the previous Governance implementation.

The current compatibility endpoints delegate to Kubernetes Operations Secret rotation flows, where effective mutation authorization is enforced by:

- `kubernetes_secrets.rotate_tls`;
- `kubernetes_secrets.bulk_rotate_tls`.

Do not use the legacy TLS keys when designing new custom roles. Removing them requires a controlled permission-deprecation migration because existing database rows, audits, or external documentation may still reference them.

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
