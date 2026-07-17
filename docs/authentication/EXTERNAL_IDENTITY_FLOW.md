# External Identity Authentication Flow

## Scope

This phase activates LDAP authentication and prepares the shared provider boundary for OIDC SSO. Local Database authentication remains permanently available for break-glass recovery.

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

The external provider verifies identity. KAORI remains authoritative for local lifecycle state and later RBAC evaluation.

## OIDC readiness

The provider schema reserves issuer, client ID, and client-secret environment references. OIDC cannot be enabled in this phase. The next phase adds redirect, callback, discovery, JWKS validation, state, nonce, issuer/audience verification, and `issuer + sub` identity linking.

## JIT policy

JIT provisioning is deliberately blocked until RBAC role mapping exists. Current LDAP onboarding is administrative provisioning only.
