# User Management

## Purpose

`app/users` owns administrative lifecycle management for KAORI user records. It does not authenticate credentials and it does not define permissions. Authentication belongs to `app/auth`; authorization and role mapping belong to `app/rbac`.

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

`users/index.html` is the page shell. Reusable sections live in `users/partials/`. Forms remain dedicated templates because they are independent workflows. Templates contain presentation branching only; business rules remain in Python.

## External-provider extension boundary

LDAP/SSO implementation must add provider discovery and identity projection services without adding provider-specific branching to `routes.py`. The next phase will define directory search, JIT provisioning, external subject binding, claim/group mapping, reconciliation, and deprovisioning.

## Known staged work

Authentication events are consolidated into Activity Audit Log under the `authentication` event type. Login success, login failure, and logout now share the operational audit presentation with provider, IP, browser, operating system, device, user-agent, result, and reason metadata. Legacy `AuthLoginEvent` persistence remains temporarily as a compatibility source, while migration `20260717_auth_activity` backfills its historical rows into the unified audit stream.

## Persistence boundary

All SQLAlchemy models remain centralized in `app/models/`. The User Management domain may import `User`, `Role`, audit, and future external-identity models from that package, but it must not define domain-local ORM models. This keeps migration discovery, model registration, and database ownership consistent across KAORI.

Future persistence additions such as `ExternalIdentityLink`, provider configuration records, account lock state, or projection-sync metadata must therefore be added under `app/models/` and referenced by `app/users` services.

## Blueprint and URL ownership

User Management is registered as the standalone `users` blueprint with the canonical URL prefix `/users`.

| Workflow | Endpoint | URL |
|---|---|---|
| Directory | `users.index` | `/users/` |
| Create | `users.create` | `/users/new` |
| Edit | `users.edit` | `/users/<id>/edit` |
| Reset password | `users.reset_password` | `/users/<id>/reset-password` |
| Activate/deactivate/restore/delete | `users.*` | `/users/<id>/<action>` |

There are no Settings wrappers, endpoint aliases, compatibility imports, or redirect shims.

## External identity implementation

The domain now owns:

- identity-provider configuration routes;
- LDAP connection validation;
- LDAP directory search;
- controlled administrative provisioning;
- external identity projection.

Persistence remains centralized in `app/models/identity.py`. LDAP protocol behavior is implemented in `app/users/providers/ldap.py`; authentication consumes it through `app/auth/providers/ldap.py`.

Canonical administration routes:

```text
/users/providers
/users/external-identities
```

OIDC fields are intentionally reserved but disabled. JIT provisioning remains blocked until the RBAC role-mapping phase.

## SSO provider administration

Google and GitHub provider configuration is managed by the Users domain, while browser authentication is owned by Authentication. Controlled SSO JIT requires a non-admin default role and provider-specific allow-list. Persistence remains centralized in `app/models/identity.py`.
