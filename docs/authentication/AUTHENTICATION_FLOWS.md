# Authentication Flows

## Credential Flow: Local Database and LDAP

```mermaid
flowchart TD
    A[POST Username and Password] --> B[CSRF and Rate Limit]
    B --> C[Credential Orchestrator]
    C --> D[Local Database Provider]
    D --> E{Local Database Identity Claims Username?}
    E -- Valid Local Credentials --> F[Normalized Success]
    E -- Local Identity Rejected --> G[Stop: Local Authority]
    E -- External Projection or No Local Identity --> H[Enabled LDAP Links]
    H --> I[LDAP User Bind]
    I --> J{Outcome}
    J -- Valid --> F
    J -- Invalid Credentials --> K[Normalized Rejection]
    J -- Provider Failure --> L[Provider Unavailable]
    F --> M[Commit Login Metadata]
    M --> N[Rotate and Establish Session]
    N --> O[Write Authentication Activity]
    O --> P[Redirect to Welcome]
```

The Local Database provider is evaluated first. A failed Local Database login stops credential dispatch when the account belongs to the Local Database; a provisioned external identity may continue to its enabled LDAP link even though its KAORI user row exists. LDAP never replaces Local Database password authority, and database outages fail closed.

LDAP authentication is link-based. KAORI loads enabled LDAP identity links case-insensitively and attempts them deterministically. `invalidCredentials` remains a credential rejection; connection, TLS, and operational bind failures become `provider_unavailable`.

## Browser SSO Flow: Google and GitHub

```mermaid
sequenceDiagram
    actor User
    participant Route as Auth Route
    participant Registry as Browser SSO Registry
    participant Provider as Google or GitHub
    participant Resolver as Identity Resolver
    participant DB as PostgreSQL
    participant Session as Session Lifecycle
    participant Audit as Activity Audit

    User->>Route: Start provider sign-in
    Route->>Registry: Resolve provider strategy
    Route->>Route: Generate state and optional nonce
    Route->>Provider: Redirect authorization request
    Provider-->>Route: Callback code and state
    Route->>Route: Validate provider, state, and TTL
    Route->>Provider: Exchange code and validate identity
    Provider-->>Resolver: Normalized SsoIdentity
    Resolver->>DB: Resolve link or controlled JIT projection
    DB-->>Resolver: Active KAORI user
    Resolver-->>Route: Normalized AuthResult
    Route->>DB: Commit login metadata
    Route->>Session: Rotate and establish session
    Route->>Audit: Record success
    Route-->>User: Redirect to Welcome
```

Google requires nonce validation. Both browser providers use a hashed state value stored in the signed session and a bounded flow lifetime. A malformed, mismatched, future-dated, or expired flow fails closed before code exchange.

## Failure Ordering

A successful authentication event is recorded only after login metadata commits and the authenticated session is established. A metadata commit failure is normalized to `database_unavailable`; KAORI does not record a false successful login.

Authentication Activity write failure is non-blocking after the security-critical login transaction has completed, but it is logged as an operational warning.

## Logout

Logout is POST-only and CSRF-protected. KAORI records the user-initiated logout, invokes Flask-Login logout, clears the complete authenticated session including step-up state and pending SSO flow state, then redirects to the login page.
