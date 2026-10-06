# Authentication security requirements

## Trust assumptions

- TLS terminates only at an approved reverse proxy or the application endpoint.
- `ProxyFix` counts exactly match trusted proxy hops; otherwise forwarded addresses are untrusted.
- PostgreSQL, Redis, and provider endpoints are on controlled networks.
- Secrets are delivered through deployment secret mechanisms, not committed configuration.
- System time is synchronized because session, OIDC, certificates, and audit chronology depend on it.

## Credential handling

- Local passwords are stored only as adaptive password hashes through Werkzeug's configured secure method.
- Plaintext credentials exist only for the request duration and are never copied to logs, audit metadata, exceptions, task queues, or notifications.
- LDAP bind secrets, OIDC client secrets, SAML keys, tokens, codes, assertions, and provider payloads follow the same rule.
- Password comparison and provider failures return normalized reason codes and generic messages.

## Session and cookie policy

- Rotate session state on every successful login.
- Use Secure, HttpOnly, SameSite=Lax cookies in production.
- Logout is a POST action protected by CSRF.
- Super-admin persistent sessions are disabled by default.
- Step-up authentication state is cleared on logout.
- Enable Flask-Login strong session protection unless compatibility testing proves otherwise.
- Define absolute and idle session timeouts before SSO activation; do not rely only on provider token lifetime.

## Brute force and lockout

The current endpoint limiter is the first layer. Production must use Redis-backed shared rate-limit storage for multi-instance deployments. The next account-security increment should add durable counters and `locked_until` without revealing whether a username exists.

Recommended policy baseline for design review:

- per-IP and per-identity throttling;
- escalating delay after repeated failures;
- time-bound lockout rather than permanent automatic disable;
- administrator unlock with Activity Log;
- break-glass account alerts rather than easily triggered permanent lockout;
- metrics for failure spikes without username leakage.

## Error handling

User-visible failures must distinguish only actionable service availability from generic credential rejection. Detailed exceptions belong in restricted application logs with a request/correlation identifier. Login Activity stores a normalized reason code, not stack traces.

## External provider requirements

LDAP requires TLS certificate validation, bounded connect/read timeouts, safe search filters, controlled bind identity, and explicit attribute mapping. OIDC requires issuer discovery validation, exact redirect URI, state, nonce, PKCE where applicable, signature and claim validation, short-lived authorization state, and no token logging. SAML requires signed assertion validation, audience/recipient checks, replay prevention, trusted metadata, and strict XML security.

## Audit requirements

Record timestamp, attempted normalized username or external subject reference, provider, success/failure, safe reason code, proxy-normalized client address, user agent, and user ID when known. Never record passwords, tokens, assertions, raw LDAP responses, cookies, or secret configuration.
