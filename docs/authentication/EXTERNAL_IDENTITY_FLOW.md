# External Identity Authentication Flow

## Scope

KAORI supports Local Database, LDAP / Active Directory, Google OpenID Connect, and GitHub OAuth authentication. Local Database remains permanently available for break-glass recovery. External providers verify identity; KAORI remains authoritative for account lifecycle and RBAC authorization.

Detailed provider configuration is documented in:

```text
docs/authentication/IDENTITY_PROVIDER_CONFIGURATION.md
```

## LDAP administrative provisioning

```mermaid
sequenceDiagram
    actor Admin
    participant UM as User Management
    participant LDAP as LDAP Directory
    participant DB as KAORI Database
    participant Audit as Activity Audit

    Admin->>UM: Open LDAP Directory Provisioning
    UM->>LDAP: Service bind and scoped search
    LDAP-->>UM: Matching identities and stable IDs
    Admin->>UM: Select identity, role, lifecycle
    UM->>DB: Create User projection
    UM->>DB: Create ExternalIdentityLink
    UM->>Audit: Record provisioning event
```

KAORI never requests or stores the user's LDAP password during provisioning.

## LDAP login

```mermaid
sequenceDiagram
    actor User
    participant Auth as Authentication
    participant DB as KAORI Database
    participant LDAP as LDAP Directory
    participant Session as Session Manager

    User->>Auth: Username and password
    Auth->>DB: Attempt Local Database authentication
    DB-->>Auth: No valid local credential
    Auth->>DB: Resolve enabled LDAP identity link
    DB-->>Auth: Provider and distinguished name
    Auth->>LDAP: User bind over LDAPS or StartTLS
    LDAP-->>Auth: Bind accepted or rejected
    Auth->>DB: Check KAORI lifecycle state
    Auth->>Session: Rotate and establish session
```

## Google and GitHub SSO login

```mermaid
sequenceDiagram
    actor User
    participant Auth as KAORI Authentication
    participant IdP as Google or GitHub
    participant DB as KAORI Database
    participant Session as Session Manager

    User->>Auth: Select SSO provider
    Auth->>Auth: Generate state and optional nonce
    Auth->>IdP: Authorization-code request
    IdP-->>Auth: Callback with code and state
    Auth->>Auth: Validate state and nonce where applicable
    Auth->>IdP: Exchange code and retrieve identity
    Auth->>DB: Resolve identity link or controlled JIT admission
    Auth->>DB: Check KAORI lifecycle state and role
    Auth->>Session: Rotate and establish session
```

## Projection and admission policy

- LDAP onboarding is administrative provisioning only.
- Google and GitHub can use pre-provisioned identity links.
- Controlled SSO JIT is optional and requires an active non-admin default role plus a provider-specific allow-list.
- Google JIT requires a verified email in an allowed domain.
- GitHub JIT requires the immutable numeric user ID or current login in the allow-list.
