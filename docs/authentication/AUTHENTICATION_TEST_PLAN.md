# Authentication test plan

## Unit tests

- Database provider returns success for a valid active local user.
- Unknown username and wrong password return the same public message and reason class.
- Deleted or inactive users cannot authenticate.
- Database exceptions return a normalized unavailable result without raw details.
- Provider registry ignores unsupported names and does not activate LDAP/SSO stubs.
- Session establishment rotates prior session data.
- Super-admin remember-me requests are ignored by default.
- Normal-user remember-me follows form intent.
- Audit writer never receives password/token fields.

## Route tests

- Login GET renders the local provider state.
- CSRF is required outside testing configuration.
- Authenticated users are redirected to Welcome.
- Successful POST redirects to Welcome and records last-login metadata.
- Failed POST renders a generic error and Login Activity.
- Rate limit returns the configured response.
- Logout rejects GET, accepts CSRF-protected POST, and removes auth plus step-up state.

## Security tests

- Username enumeration is not possible through body, status, or meaningful timing differences.
- Forwarding headers are not trusted without configured ProxyFix.
- Session identifier/state changes after login.
- Production cookies contain Secure, HttpOnly, and SameSite attributes.
- Passwords, cookies, tokens, assertions, and provider payloads do not appear in logs or audit rows.
- Open redirect attempts cannot control the post-login destination.
- Break-glass account cannot retain a persistent session by default.

## Integration tests before LDAP/SSO activation

- TLS validation failures fail closed.
- Timeout and provider outage produce normalized unavailable behavior.
- OIDC state/nonce/signature/audience/issuer checks reject invalid callbacks.
- LDAP filters are escaped and group values normalized.
- External identity projection is stable across mutable email/display-name changes.
- Role mapping conflicts and removal behavior match the RBAC contract.

## Operational validation

- Redis-backed limiter is shared across production web instances.
- Proxy hop counts match the deployed ingress path.
- Login Activity retention/archive lifecycle works without deleting unarchived evidence.
- Break-glass validation is rehearsed and evidenced under change control.
