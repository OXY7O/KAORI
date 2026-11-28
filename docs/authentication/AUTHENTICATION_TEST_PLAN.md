# Authentication Test Plan

## Automated Function Tests

The canonical suite is `tests/access/authentication/`.

### Provider Core

- Catalog maps concrete types to `database`, `ldap`, and `sso` families.
- Catalog and runtime browser registry contain the same browser-provider types.
- Unsupported provider types fail closed.
- Provider-form projection writes only fields owned by the selected provider type.
- Provider validation normalizes configuration and protocol failures.

### Credential Orchestration

- Local success is authoritative.
- An existing local identity with a wrong password does not fall through to LDAP.
- Unknown local identity or an existing externally provisioned LDAP account may continue to enabled, linked LDAP providers; the presence of its KAORI projection row does not grant local password authority.
- Database unavailability stops external lookup.
- LDAP provider unavailability is preserved after all external attempts.
- Enabled → Disabled external provider transitions atomically advance auth_session_version only for externally owned linked identities; disabling an already disabled provider, ordinary edits and re-enabling do not rotate generations.
- Old browser and remember cookies fail closed on the next request across app instances; enabling again cannot restore previous generations.
- Provider disablement does not revoke unrelated providers' user projections or Local Database break-glass users. If the same KAORI external account links multiple provider instances of the same source, its sessions are conservatively revoked upon disabling any linked provider; no credential authority is transferred.
- A revocation update or provider commit failure rolls back the transaction; the Activity Audit event records a count of linked accounts, not the number of active sessions.

### Local Database Provider

- Valid active user succeeds.
- Unknown username and wrong password have the same public rejection.
- External-source user does not receive Local Database password ownership.
- Inactive user is rejected.
- SQLAlchemy failure becomes `database_unavailable` and rolls back.

### LDAP

- URI, port, LDAPS, StartTLS, TLS certificate validation, timeout, and bind-secret handling are covered.
- Search input is escaped and filter placeholders are constrained.
- Stable binary subjects are normalized deterministically.
- User bind distinguishes invalid credentials from provider outage.
- Enabled links are matched case-insensitively and tried deterministically.
- Inactive, storage failure, invalid credentials, and provider-unavailable outcomes are normalized.

### Browser SSO

- Strategy registry is explicit and consistent with the catalog.
- Authorization URLs contain required state, scope, callback, and nonce behavior.
- Raw state is not persisted.
- Provider ID, state hash, start timestamp, future timestamp, malformed values, and TTL are validated fail-closed.
- Provider lookup storage failure is normalized.
- Existing identity links, inactive users, controlled JIT, conflicts, and commit failures are covered.

### Session, Readiness, and Identity Ownership

- Successful login clears prior session state and establishes a fresh session.
- A successful Local, LDAP or SSO login atomically increments its own user's session generation; old signed browser and remember cookies are denied on the next request while unrelated accounts remain authenticated.
- Concurrent login transactions for the same user serialize generation increments. The response must bind to **its own** UPDATE RETURNING generation rather than an ORM refresh that could observe the newer login's generation.
- Failed credentials, account disabled/deleted before issuance, source mismatch or SQL error must not commit a replacement generation or permit a new authenticated session.
- A Local Database proof verified before a password rotation must not issue a session after rotation. Compare the request-local verified hash to the locked current credential; same-current-credential independent logins retain latest-generation semantics. Pending MFA final issuance must compare the original pending generation, even after factor verification commits or the ORM reloads. Reject invalid/missing proof, inactive role and stale generations; never put a password hash in a cookie or audit. Map the source regressions to `tests/access/authentication/test_single_session_generation.py`; PostgreSQL and real browser concurrency remain separately required.
- The non-secret login-specific `auth_session_ref` is safe in successful login, logout and system-owned session-expiry Activity Audit. A failed login may name a target user but cannot inherit authenticated actor or active-session correlation from other sessions.
- Multiple browser tabs sharing the same copied signed cookie are out of scope for the one-login-generation guarantee; test that distinction rather than describing the feature as one physical device.
- Guided two-browser UAT verifies Browser A login then Browser B login as the same user, A rejected, B allowed, optional remember-me old cookie rejected, independent user unaffected and clean audit correlation; also exercise two parallel login requests and provider-disable/password-change regressions.
- Privileged Admin/Super Admin Remember Me is denied; ordinary Remember Me may only restore the still-valid generation within both server deadlines. Legacy cookies without issuance/activity timestamps must sign in again.
- Test idle at and immediately before the deadline, passive polling/status with no activity, explicit CSRF activity touch, continuous activity crossing absolute expiry, and exact-generation concurrent touch/logout/new login. Reopening a browser with or without restore or Remember Me cannot exceed the server deadlines. Confirm expiry audit is system-owned and secret-free, logout replay fails, policy no-op retains sessions and a policy change invalidates existing generations, and DB failure denies without claiming successful revocation. Qualification requires actual browser, database and multi-instance evidence.
- Logout clears auth and step-up state.
- Readiness requires every table touched by the login path.
- Concrete SSO sources map to the SSO family.
- Unknown sources cannot manage a KAORI password.

### Architecture Contracts

- LDAP protocol code belongs to `app/access/authentication`.
- Combined OAuth module and Users-owned LDAP package remain absent.
- User routes delegate provider projection/validation to Authentication.
- Routes use strategy lookup and shared SSO flow validation rather than provider branches.
- ORM models do not duplicate catalog predicates.

## Route and Integration Tests

Run inside the KAORI dev container:

```bash
pytest -q tests/access/authentication
pytest -q tests/access/authentication --cov=app.access.authentication --cov-report=term-missing
```

Route/integration coverage must verify CSRF, login GET/POST, authenticated redirect, login metadata, normalized flashes, rate-limit responses, SSO start/callback, POST-only logout, and Activity Audit records.

## Manual Provider Matrix

Test Local Database, LDAP, Google OIDC, and GitHub OAuth with:

- valid active identity;
- wrong credential or denied authorization;
- inactive KAORI projection;
- disabled provider;
- provider disabled **while already signed in** (old session rejected on next request; fresh login blocked; re-enable requires new session);
- missing secret;
- PostgreSQL unavailable;
- external endpoint unavailable or TLS failure;
- pre-provisioned identity;
- JIT allowed and JIT denied;
- duplicate username/email/subject conflict;
- expired or mismatched SSO callback state.

## Operational Validation

- Redis-backed limiter is shared across production web instances.
- Trusted proxy hop counts match the deployed ingress path.
- Authentication Activity retention/archive lifecycle preserves required evidence.
- Local super-admin recovery is rehearsed under change control.

### Session lifecycle qualification (#5284)

After applying migration `20261128_auth_session_expiry` to the Dev Container database and restarting the application, verify the following against the committed defaults. Existing cookies without trusted timestamps must sign in again.

- Privileged and ordinary sessions: idle expiry, absolute expiry despite interaction, warning and Continue Session (idle only).
- Passive polling and background refresh cannot extend idle; trusted foreground activity may extend idle without resetting absolute age.
- Close and restore the browser, with and without Remember Me; verify no restored session bypasses either deadline. Browser closure alone is not a revocation signal.
- Replay a revoked generation after explicit logout, new sign-in, policy change and provider disablement; verify an older request cannot revoke the newer generation.
- Save an unchanged policy and confirm existing sessions remain valid; save a changed policy and verify fresh authentication is required. Verify read-only roles cannot modify the policy and CSRF is enforced.
- Confirm Session Security Activity Audit entries are system-owned for expiry, classified as security-control evidence and contain no cookies or credentials.
- Exercise Local, LDAP and browser SSO, PostgreSQL concurrency, multiple app instances, desktop/mobile warning and HTMX expiry. Record actual results, timestamps and evidence before marking qualified.


## Account lockout administrative qualification (AL-03, #5326)

- [ ] Singleton migration preserves existing MFA, bot and session configuration; existing mode remains Disabled.
- [ ] Viewer, unauthorized direct POST, external administrator, stale generation, remembered/non-fresh session, missing CSRF, invalid reason/reference and replayed TOTP cannot mutate policy or account state.
- [ ] Default authorization switches reject active modes; Enforced requires Monitor Only plus separate authorization, working Redis script probe and enrolled local recovery administrator.
- [ ] Policy revision increments exactly once on change; stale forms and concurrent policy/credential/admission operations fail closed. No-op does not change revision or revoke sessions.
- [ ] User lockout visibility is permission-scoped; self, external, inactive, deleted, Super Admin and unauthorized privileged-target unlock attempts are rejected. Exact active deadline and revision required.
- [ ] State, factor replay consumption and audit/Notification Deck evidence roll back together on write/commit failure; successful unlock preserves lifecycle, credentials and existing sessions.
- [ ] Verify actual hosted Redis/DB concurrency, policy writer lock order, role revocation, UI/light/dark/responsive/accessibility, notification projection, and independent all-sessions-expired recovery with Turnstile/Redis unavailable (#4014). Production activation remains HOLD until acceptance.


## AL-04 Login Protection resilience qualification (#5416)

- [ ] With all administrator sessions expired, verify shared Redis failure denies new web admission, without fallback or changing committed mode; inspect independent per-IP limiter behavior across app instances.
- [ ] Under isolated approved management access, verify default denial, interactive process authorization, local Super Admin password and unused TOTP, declared operator/incident evidence and explicit revision/impact acknowledgement.
- [ ] In Monitor Only or Enforced, rollback commits Disabled and exactly one revision increment with MFA replay state and correlated audit/notification; no-op with fresh proof preserves revision. Stale revision, replay, missing evidence, wrong/expired account and HTTP use fail closed.
- [ ] Inject audit/commit failure and concurrent policy writer/credential admission/rollback; verify atomic state, no false success, existing session and unrelated controls unchanged, and no Redis changes.
- [ ] Validate targeted-spray behavior for known/unknown/local Super Admin, collisions, shared NAT/IP and independent infrastructure mitigation; verify no enumeration or remotely induced permanent account lock.
- [ ] Restore Redis through approved infrastructure path; qualify actual CLI bootstrap during outage, normal admission and controlled Monitor Only → Enforced reactivation. Record exact-SHA evidence and Human Acceptance. Activation HOLD until all relevant qualification passes.


## AL-05 authentication abuse signal qualification (#5420)

- [ ] Disabled flag makes no snapshot or notification write; actual existing maintenance worker schedule and runtime environment are qualified before opt-in.
- [ ] Verify exact closed window, late commit/retention gaps, sample cap and missed-window partial posture, source diversity and known-target count without identity disclosure, and no double counting lock threshold as a credential rejection.
- [ ] Separate invalid credential outcome, CAPTCHA/endpoint rate limit, identity-budget observation, MFA, provider outage and enforced/monitor threshold; targeted recovery-principal and multi-source/target patterns remain indications, not verified attacks.
- [ ] Concurrent worker retries produce one snapshot/window and bounded operator notifications atomically; rollback on notification or commit failure, stale/missing evidence cannot be read as healthy.
- [ ] Verify PostgreSQL query plan/load at abusive event volume, receipt/permission boundaries, no raw identity/credential output, partial/recipient cap evidence, existing Kubernetes signal regression, no public/login-path or external channel mutation.
- [ ] Review initial observation thresholds with security owner. Native AlertCase recommendation/routing, external delivery and stronger recovery-account throttling are separate scope. Record exact-SHA hosted evidence and Human Acceptance.


## AL-05B reserved central source contract (#5423)

- [ ] Verify Rule Catalog and coverage dialog show Reserved Plan / Not admitted, domain-owned rather than provider instance; no active finding or case while reserved.
- [ ] Verify candidate validation rejects missing, disabled, stale, partial, malformed, previous-window and inconsistent indicators/counts; allowlist aggregate values only, no individual identifiers. Quiet evidence is not verified recovery.
- [ ] Verify current local Super Admin and Intelligence permission, no worker/no-request/unauthorized source access, no direct promotion or override activation, no direct case mutation/read or firing/resolved delivery for the unadmitted domain.
- [ ] Qualify AL-05 committed worker evidence, query load, late commits, privacy and actual source freshness; security owner approves rule before Available. Separate scoped case authorization, lifecycle, routing and external delivery qualification before case admission.
