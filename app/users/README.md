# User Management

## Purpose

`app/users` owns administrative lifecycle management for KAORI user records. It does not authenticate credentials and it does not define permissions. Authentication belongs to `app/auth`; authorization and role mapping belong to `app/rbac`. The Access control plane groups User Management and Identity Providers in navigation, while this package remains the canonical user/provider administration implementation.

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

| File               | Responsibility                                                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`      | Package marker and stable public exports only.                                                                         |
| `routes.py`        | User Management HTTP boundary, permission decorators, form orchestration, redirect/HTMX responses, and toast delivery. |
| `forms.py`         | Administrative form validation and provider-aware fields. It must not query providers or persist users.                |
| `service.py`       | User queries, pagination, mutation helpers, administrative guardrails, and audit-event preparation.                    |
| `identity.py`      | Canonical Local/LDAP/SSO identity-source definitions and credential ownership.                                         |
| `lifecycle.py`     | Canonical active, inactive, deleted, and administrative-tier presentation.                                             |
| `notifications.py` | Standard User Management toast and Activity Audit payload construction.                                                |
| `provider_forms.py` | Maps the provider WTForms surface into the Auth-owned provider configuration DTO.                                      |

## Identity sources

- `database`: active. KAORI is credential owner and source of truth.
- `ldap`: active administrative identity projection. LDAP/Active Directory remains source of truth for credentials.
- `google_oidc`: active Google browser SSO projection. Google remains source of truth for the external identity.
- `github_oauth`: active GitHub browser SSO projection. GitHub remains source of truth for the external identity.

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

Provider discovery, external subject binding, LDAP directory search, administrative LDAP provisioning, and controlled Google/GitHub JIT are implemented. Protocol behavior remains in Auth provider adapters; Users owns only administration forms, lifecycle orchestration, and projection requests. Generic OIDC, SAML, group/claim mapping, reconciliation, and deprovisioning remain future extensions.

## Known staged work

Authentication events are stored only in Activity Audit Log under the `authentication` event type. Login success, login failure, and logout share the same audit presentation with provider, IP, browser, operating system, device, user-agent, result, and reason metadata. User account summaries query this canonical event stream directly.

## Persistence boundary

All SQLAlchemy models remain centralized in `app/models/`. The User Management domain may import `User`, `Role`, audit, and future external-identity models from that package, but it must not define domain-local ORM models. This keeps migration discovery, model registration, and database ownership consistent across KAORI.

Existing `IdentityProvider` and `ExternalIdentityLink` records remain under `app/models/identity.py`. Future additions such as durable account-lock state, group/claim mapping, or projection reconciliation metadata must also be added under `app/models/` and consumed through domain services.

## Blueprint and URL ownership

User Management is registered as the standalone `users` blueprint with the canonical URL prefix `/users`.

| Workflow                           | Endpoint               | URL                          |
| ---------------------------------- | ---------------------- | ---------------------------- |
| Directory                          | `users.index`          | `/users/`                    |
| Create                             | `users.create`         | `/users/new`                 |
| Edit                               | `users.edit`           | `/users/<id>/edit`           |
| Reset password                     | `users.reset_password` | `/users/<id>/reset-password` |
| Activate/deactivate/restore/delete | `users.*`              | `/users/<id>/<action>`       |

There are no Settings wrappers, endpoint aliases, compatibility imports, or redirect shims.

## External identity implementation

The domain now owns:

- identity-provider configuration routes;
- provider administration and validation initiation;
- LDAP directory search;
- controlled administrative provisioning;
- external identity projection.

Persistence remains centralized in `app/models/identity.py`. LDAP protocol behavior is owned by `app/auth/providers/ldap.py`; User Management consumes that boundary for validation, directory search, and administrative projection.

Canonical administration routes:

```text
/users/providers
/users/external-identities
```

LDAP users are administratively provisioned before credential authentication. Google and GitHub may use pre-provisioned links or controlled JIT with a non-admin default role and provider-specific allow-list.

## Identity provider UI structure

The provider form is split so provider-specific UI remains traceable and only active controls are submitted:

| File                                                          | Responsibility                                                                                                                    |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `templates/users/providers/form.html`                         | Add/Edit page shell, standardized hero, two-column composition, and save actions.                                                 |
| `templates/users/providers/partials/_provider_selector.html`  | Explicit LDAP, Google, and GitHub provider cards backed by the `provider_type` form field.                                        |
| `templates/users/providers/partials/_ldap_configuration.html` | LDAP-only connection, TLS, search, and attribute-mapping fields.                                                                  |
| `templates/users/providers/partials/_sso_configuration.html`  | SSO credentials, JIT role, Google-domain policy, and GitHub-subject policy.                                                       |
| `templates/users/providers/partials/_registry.html`           | Shared KAORI provider registry with server-side Search / Type / State filtering, loading evidence, and expandable rows.            |
| `templates/users/providers/partials/_provider_detail.html`    | Expanded provider identity, authentication contract, projection evidence, and administrative actions.                             |
| `templates/users/providers/partials/_directory_provisioning_strip.html` | Full-width LDAP provisioning workflow strip between provider posture and the registry.                                      |
| `templates/users/providers/partials/_provider_guidance.html`  | Sticky provider-form guidance with default-collapsed setup summaries, callback evidence, and runbook reference.                    |
| `static/js/identity_provider_form.js`                         | Provider selection, panel visibility, inactive-control disabling, JIT policy selection, callback preview, and dynamic SSO labels. |

Full administrator configuration is documented in `docs/authentication/IDENTITY_PROVIDER_CONFIGURATION.md`.

## Identity Providers refinement baseline

The Identity Providers review keeps the page open for final Access UI lock while establishing the following presentation contract:

- the hero uses the shared Inventory-style KAORI `page_hero.context_card()` pattern;
- Provider Registry Overview separates configuration completeness, enablement, provider family, and identity-link evidence;
- the Provider Registry uses shared KAORI table/filter/loading/detail/pagination components, server-side HTMX filtering, and the standard 5/10/25/50 Rows contract;
- `Enabled` and `Configured` are independent states; KAORI does not claim durable `Validated` readiness because provider validation results are currently on-demand operational feedback rather than persisted provider evidence;
- provider detail surfaces may display environment-variable references, but never runtime secret values;
- LDAP Directory Provisioning remains a child workflow of Identity Providers and local KAORI role assignment remains the authorization boundary;
- the provider index is a full-width operational workspace: authentication/provider-family guidance is consolidated into Provider Registry Overview, while Directory Provisioning is a horizontal workflow strip above the registry;
- LDAP Setup Guidance opens by default as a shared KAORI box-flow; Google/GitHub guidance and the technical runbook remain collapsed, while form right rails remain sticky at `xl:top-5`. Add/Edit forms can test current values before Save without persisting validation posture.

This refinement is not the Identity Providers Final Lock. Directory Provisioning and remaining Access child pages are still reviewed independently before Access is final-locked.

## SSO provider administration

Google and GitHub provider configuration is managed by the Users domain, while browser authentication is owned by Authentication. Controlled SSO JIT requires a non-admin default role and provider-specific allow-list. Persistence remains centralized in `app/models/identity.py`.

## User Management refinement baseline

The User Management review keeps the page open for final Access UI lock while tightening the operational contract:

- Restore and Activate are separate lifecycle decisions. Restore clears `deleted_at` but returns the account to **Inactive**.
- Deactivate, delete, and super-admin demotion serialize the active-super-admin rows with a database `FOR UPDATE` boundary before the final last-super-admin check.
- The directory uses shared KAORI loading, filter, table-label, expandable-detail, destructive-confirmation, and pagination contracts.
- Inactive roles remain visible in the directory filter so operators can locate users assigned to a fail-closed role.
- User-directory mutations update the hero posture out-of-band so account counts do not remain stale after HTMX actions.

This refinement is not the User Management Final Lock. The page remains open until Access child pages are reviewed independently.

## Legacy AuditEvent Boundary

User Management still writes the legacy `AuditEvent` row in the primary mutation transaction and also emits the Notification-backed operational feedback used by Activity Audit / Notification Center. `AuditEvent` is still consumed by Jobs, TLS Governance, Intelligence, Resolver, Knowledge, and other domains, so it **must not be removed from User Management in isolation**. Consolidation requires a separate cross-domain audit-ledger migration.

## Password Reset Session Boundary

Account deactivation and soft deletion take effect on the next authenticated request because the Flask-Login user loader rejects inactive/deleted users. A Local Database password reset changes the credential immediately, but **existing authenticated sessions are not yet version-invalidated** because KAORI does not currently persist a session/security generation on `User`. This security-hardening decision must be resolved before User Management Final Lock rather than being hidden inside a page-only refinement.
