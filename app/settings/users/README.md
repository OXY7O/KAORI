# User Management

## Purpose

`app/settings/users` owns administrative lifecycle management for KAORI user records. It does not authenticate credentials and it does not define permissions. Authentication belongs to `app/auth`; authorization and role mapping belong to `app/rbac`.

## Current scope

- Administratively create Local Database users.
- Edit identity metadata and assigned role.
- Activate or deactivate accounts.
- Soft-delete accounts.
- Reset Local Database passwords.
- Protect self-management, administrator-level accounts, and the last active super admin.
- Record every mutation in Activity Audit Log and return all operator feedback through the standard toast.

Self-registration is not supported.

## File responsibilities

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker and stable public exports only. |
| `routes.py` | User Management HTTP boundary, permission decorators, form orchestration, redirect/HTMX responses, and toast delivery. |
| `forms.py` | Administrative form validation and provider-aware fields. It must not query providers or persist users. |
| `service.py` | User queries, pagination, mutation helpers, administrative guardrails, and audit-event preparation. |
| `identity.py` | Canonical Local/LDAP/SSO identity-source definitions and credential ownership. |
| `lifecycle.py` | Canonical active, inactive, deleted, and administrative-tier presentation. |
| `notifications.py` | Standard User Management toast and Activity Audit payload construction. |

## Identity sources

- `database`: active. KAORI is credential owner and source of truth.
- `ldap`: planned identity projection. LDAP/Active Directory remains source of truth.
- `sso`: planned identity projection. The IdP remains source of truth.

External provider records must never contain a KAORI password. The form may display credential ownership, but password inputs must be disabled and omitted from submission for LDAP/SSO.

## Lifecycle and administrative controls

Lifecycle and privilege are separate axes:

- Lifecycle: active, inactive, soft-deleted.
- Administrative tier: standard, admin, super admin.
- Identity source: Local Database, LDAP, SSO.

`is_super_admin` is an explicit emergency/platform authority flag. It is not a substitute for a normal role and cannot be changed by a non-super-admin actor. The last active super admin cannot be disabled, demoted, or deleted.

## Notification contract

User Management must not call Flask `flash()`. Every create, update, activate, deactivate, reset-password, and soft-delete action emits:

1. a top-right KAORI operational toast;
2. a persistent Activity Audit record;
3. a safe metadata payload without passwords or provider tokens.

## Template structure

`settings/users/index.html` is the page shell. Reusable sections live in `settings/users/partials/`. Forms remain dedicated templates because they are independent workflows. Templates contain presentation branching only; business rules remain in Python.

## External-provider extension boundary

LDAP/SSO implementation must add provider discovery and identity projection services without adding provider-specific branching to `routes.py`. The next phase will define directory search, JIT provisioning, external subject binding, claim/group mapping, reconciliation, and deprovisioning.

## Known staged work

Authentication event consolidation into Activity Audit Log is the target. The separate navigation entry is removed in this stage. The legacy `AuthLoginEvent` persistence remains temporarily until a migration can preserve historical records and archive semantics without data loss.
