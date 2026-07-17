# Authentication flows

## Local database login activity

```mermaid
flowchart TD
    A[Open login page] --> B{Already authenticated?}
    B -- Yes --> C[Role-aware Welcome]
    B -- No --> D[Submit local credentials]
    D --> E[CSRF and form validation]
    E -- Invalid --> F[Safe validation response]
    E -- Valid --> G[Rate-limit decision]
    G -- Blocked --> H[Generic throttling response]
    G -- Allowed --> I[Local provider query]
    I --> J{Database available?}
    J -- No --> K[Record service failure]
    K --> L[Temporary unavailable response]
    J -- Yes --> M{Password and account valid?}
    M -- No --> N[Record normalized failure]
    N --> O[Generic invalid-login response]
    M -- Yes --> P[Record successful attempt]
    P --> Q[Update last-login metadata]
    Q --> R[Rotate and establish session]
    R --> C
```

## Local login sequence

```mermaid
sequenceDiagram
    actor User
    participant Route as Auth route
    participant Service as Auth service
    participant Registry as Provider registry
    participant DBP as Database provider
    participant Audit as Login Activity
    participant Session as Session manager
    participant Welcome as Welcome/RBAC

    User->>Route: POST username/password + CSRF
    Route->>Service: authenticate(username, password)
    Service->>Registry: resolve active providers
    Registry-->>Service: local provider
    Service->>DBP: authenticate()
    DBP-->>Service: normalized AuthResult
    Service-->>Route: AuthResult
    Route->>Audit: record safe result
    alt successful and active
        Route->>Session: rotate + login user
        Route->>Welcome: redirect
    else rejected
        Route-->>User: generic safe error
    end
```

## Planned external login

SSO browser redirects and LDAP password authentication have different transport flows but must converge on one normalized identity result. After verification, KAORI resolves or provisions the local user projection, applies explicit role mapping, checks local account state, records Login Activity, and establishes the KAORI session. Failure of an external provider must retain access to the separately controlled local login path.

## Logout

Logout requires POST plus CSRF, invokes Flask-Login logout, removes auth-source and step-up session state, and redirects to login. It must not be implemented as an idempotent GET link because cross-site navigation could otherwise terminate sessions.
