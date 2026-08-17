# Authentication Architecture

## Objective

KAORI uses a provider-neutral authentication architecture in the Access domain. Provider identity and technical protocol are intentionally separate so new identity products can reuse existing protocol adapters without refactoring User Management, RBAC, routes, or persistence.

The canonical hierarchy is:

```text
Access
→ Identity Provider
→ Provider
→ Adapter
→ Authentication / Directory Flow
→ External Identity Projection
→ KAORI User
→ RBAC
```

Identity Provider follows the same architectural principle as KAORI infrastructure Integrations, but it remains under the authentication boundary rather than `app/integrations/`.

## Context and Boundary

```mermaid
flowchart LR
    Browser --> AuthRoutes[Auth Routes]
    AuthRoutes --> CredentialRegistry[Credential Adapter Registry]
    AuthRoutes --> BrowserRegistry[Browser Adapter Registry]

    CredentialRegistry --> LocalDatabase[Local Database]
    CredentialRegistry --> DirectoryCredential[Directory Credential Adapter]

    BrowserRegistry --> BrowserAdapter[Browser SSO Adapter]
    BrowserAdapter --> IdentityResolution[External Identity Resolution]
    DirectoryCredential --> IdentityLinks[External Identity Links]
    IdentityResolution --> IdentityLinks

    Admin[Identity Provider Workspace] --> DirectoryRegistry[Directory Adapter Registry]
    DirectoryRegistry --> DirectoryAdapter[Directory Adapter]
    DirectoryAdapter --> ProjectionProof[Signed Projection Proof]
    ProjectionProof --> IdentityLinks

    IdentityLinks --> UserProjection[KAORI User Projection]
    AuthRoutes --> Session[Session Lifecycle]
    UserProjection --> RBAC[RBAC and Permissions]
    AuthRoutes --> Audit[Authentication Activity Audit]
```

## Canonical Provider Vocabulary

`app/definitions/catalogs/auth/identity_provider/providers.yaml` is the source-controlled provider catalog. `app/auth/identity_provider/catalog.py` is its runtime vocabulary loader.

Every provider definition separates:

- `provider_key` — product/authority identity;
- `adapter_key` — technical implementation contract;
- `family` — `database`, `directory`, or `sso`;
- `flow` — `credentials` or `browser`;
- `configuration_profile` — configuration shape;
- `admission_policy` — projection/JIT admission contract.

Examples:

```text
provider_key=google          adapter_key=google_oidc
provider_key=github          adapter_key=github_oauth2
provider_key=ldap_directory  adapter_key=ldap
provider_key=database        adapter_key=local_database
```

Product identity must not be encoded in core form branches, route branches, or ORM columns.

## Code Ownership

### Authentication Kernel

`app/auth/identity_provider/` owns provider vocabulary, adapter protocols, adapter registries, provider-specific protocol implementations, and normalized authentication/directory outcomes.

Reusable protocols live under:

```text
app/auth/identity_provider/adapters/<adapter>/
```

Provider-specific behavior lives under:

```text
app/auth/identity_provider/providers/<provider>/
```

### Identity Provider Workspace

`app/identity_providers/` owns provider administration, validation, directory search, signed administrative identity projection, and workspace presentation.

Its canonical UI is `/access/identity-providers` with:

```text
Overview · Providers · Directory Provisioning
```

### User Management

`app/users/` owns KAORI user lifecycle, effective access presentation, and role assignment. It does not own provider configuration.

### RBAC

RBAC owns roles, permissions, route guards, menu visibility, and operational authorization. Provider adapters must not assign hidden permissions. `is_super_admin` is reserved for Local Database break-glass identities.

## Adapter Registries

KAORI maintains separate registries because the protocol contracts are different:

- credential adapter registry;
- browser SSO adapter registry;
- directory adapter registry.

Application routes dispatch using `adapter_key`; they do not instantiate LDAP, Google, GitHub, or future products directly.

## Provider Lifecycle

1. **Registered** — provider identity and adapter contract exist.
2. **Configured** — required non-secret configuration and secret references exist.
3. **Validated** — adapter-level connectivity/protocol and admission-policy checks pass.
4. **Enabled** — new authentication/provisioning attempts may use the provider.
5. **Review Required** — enabled configuration, JIT/admission, or projection posture is incomplete.
6. **Disabled** — new attempts are rejected while identity links and audit evidence remain.

## Error Normalization

Protocol exceptions never cross the HTTP boundary directly.

Examples include:

- invalid password → `invalid_credentials`;
- inactive linked user → `user_inactive`;
- database failure → `database_unavailable`;
- external protocol outage → `provider_unavailable`;
- missing projection/admission failure → `identity_not_provisioned`;
- browser callback failures → explicit normalized SSO reason codes.

## Redirect Contract

Successful authentication routes to `welcome.index`. Authentication does not encode role-specific destination logic. Every destination independently applies server-side permission checks.

## Extension Contract

Adding a new identity product must follow this order:

1. add or reuse an adapter;
2. add a provider definition to the source-controlled catalog;
3. add provider-specific implementation only when the provider has behavior beyond the reusable adapter;
4. add provider-specific guidance partial when needed;
5. validate catalog/registry/contracts.

Core routes, User Management, RBAC, and database schema must remain unchanged when an existing adapter can serve the provider.
