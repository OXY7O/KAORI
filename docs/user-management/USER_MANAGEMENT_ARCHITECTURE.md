# User Management Architecture

## Boundary

```mermaid
flowchart LR
    Admin[Authorized administrator] --> Routes[User Management routes]
    Routes --> Policy[Lifecycle guardrails]
    Routes --> Service[User administration service]
    Service --> Users[(KAORI users)]
    Service --> Audit[Activity Audit]
    Routes --> Toast[Operational toast]
    Auth[Authentication] --> Users
    Users --> RBAC[RBAC authorization]
```

User Management owns administrative records. Authentication verifies identity. RBAC decides what an authenticated user may do.

## Identity administration model

Local users are native identities. LDAP and SSO users are external identity projections. KAORI stores only the local projection, lifecycle override, assigned role, and provider linkage needed for authorization and audit.
