# Break-glass super-admin runbook

## Purpose

The break-glass account restores administrative access when LDAP, SSO, provider mapping, or identity infrastructure is unavailable. It is a local database account and must not depend on external identity services.

## Required controls

- Maintain at least one explicitly designated local break-glass account.
- Store its high-entropy credential in an approved offline or privileged secret-management process.
- Do not use it for routine operations.
- Disable persistent login and use a short administrative session.
- Protect the final break-glass account from deletion, disablement, external-provider conversion, and loss of super-admin status.
- Generate high-visibility Login Activity and an operational security notification on every use.
- Require a reason/ticket for post-login privileged operations where supported.

## Activation procedure

1. Confirm external authentication or mapping failure through independent evidence.
2. Open the direct local login endpoint over the approved management network.
3. Retrieve the credential using the organization’s dual-control procedure.
4. Authenticate and verify that Login Activity records the local provider and client context.
5. Repair provider configuration or role mapping; avoid unrelated changes.
6. Validate normal administrator access through the restored provider.
7. Logout the break-glass session.
8. Rotate the credential if exposure policy requires it.
9. Attach audit evidence and remediation notes to the incident/change ticket.

## Recovery validation

At a controlled interval, validate that the account exists, is active, remains local, retains super-admin authority, can authenticate, creates audit evidence, and cannot create a persistent session. A test must not expose the credential to normal application logs.

## Current implementation note

The schema currently distinguishes `is_super_admin` but not `is_break_glass`. Until the dedicated marker and safeguards are implemented, local super-admin accounts receive the stricter persistent-session policy. The dedicated migration should be performed together with RBAC/role-mapping safeguards.


## Login Protection recovery (#4015 / #5326)

Local Super Admin is excluded from durable password lockout, not from CAPTCHA, MFA, shared identity budget or existing per-IP limits. Preserve an independent management-plane recovery capability; the public login is not an emergency bypass.

For an existing authorized, fresh Local Database administrator session with enrolled authenticator, use Access → Authentication Security → Bot Protection → Login Protection. Select Disabled, provide incident/change reference, non-sensitive reason, current password, unused TOTP and acknowledgement. This web operation still depends on the existing administrative request limiter; it is not independent recovery if Redis is unavailable. Verify committed mode/revision and Activity Audit; confirm normal login and unchanged MFA/session/lifecycle policy. To unlock one ordinary local account, use User Management → Details → Login Protection → Unlock Account; verify the target and active deadline. Unlock does not reset the password or upstream directory state. Preserve incident evidence and investigate ongoing password spray.

Do not set either activation authorization switch until the relevant approved hosted qualification, recovery drill, and operational acceptance are recorded. Monitor Only precedes Enforced. Re-enable only after Redis script, shared topology, proxy trust, capacity, provider/normal login, protected recovery, and concurrent state/audit checks are validated against the deployed candidate. The environment switch alone does not change the committed mode and must never be treated as emergency rollback.

**Recovery dependency:** #4014 provides a scoped source implementation for Turnstile outage recovery below. It is not yet runtime-qualified. Redis outage and targeted-login-spray recovery remain separate scenarios; keep Login Protection activation HOLD until they are qualified.


## Isolated Bot Protection recovery (BP-03, #4014)

Use this procedure only after exact-image hosted qualification and explicit incident/change authorization. The command runs through the existing Flask CLI, not HTTP, does not issue an authenticated session, and needs no prior browser session. It changes only the committed Bot Protection mode and invalidates previous provider test evidence. It does not disable MFA, Login Protection, per-IP/shared rate limiting, change credentials, or provide arbitrary database access.

### Prerequisites

- Approved bastion/management access to the admitted KAORI runtime; restrict container exec/shell to named emergency operators, record operator authorization and dual-control custody in independently retained management logs. The CLI cannot independently attest bastion identity, isolation, or approval.
- Healthy authoritative PostgreSQL and accessible existing MFA encryption authority. Active Local Database Super Admin with known current password and an enrolled, usable TOTP authenticator. Do not reset the password or remove MFA merely to use this procedure.
- Incident/change ticket, non-sensitive reason, and named operator reference; separate operator access log links the named operator to the authenticated KAORI principal. The entered operator reference is declared, not verified by the application.
- Keep `AUTH_BREAK_GLASS_RECOVERY_ALLOWED=false` in persistent environment files. Explicitly authorize a single interactive CLI process only. Do not use a shared web environment, non-interactive pipe, credential-bearing command arguments, recorded terminal input, or a public recovery endpoint. Limit attempts via management access controls; one proof attempt per CLI invocation.

### Controlled recovery procedure

1. Confirm Turnstile outage using independent evidence; record the affected environment, immutable build SHA, policy state and incident/change authorization. Prefer the existing authorized UI when available.
2. Using the approved management-plane execution mechanism, open an interactive terminal for the **exact affected admitted application runtime**, with the same database and MFA encryption configuration. On a governed Compose host, after selecting the existing correct project and compose files using the approved deployment adapter, invoke:

   ```bash
   docker compose exec -e AUTH_BREAK_GLASS_RECOVERY_ALLOWED=true web flask --app run:app recover-bot-protection
   ```

   This is an illustrative invocation within the already selected project, not a standalone deployment command. No persistent environment changes or service restart are required. On an approved non-Compose runtime use the equivalent single-process environment override.

3. Supply the local Super Admin username, named management operator reference, incident/change ticket and non-sensitive reason. Review the explicit confirmation. Enter password and unused TOTP via hidden terminal prompts only.
4. A successful exit reports the committed previous/new mode and audit correlation. Verify Activity Audit and the actor's Notification Deck. A repeated request with valid new proof against Disabled records an unchanged result; it does not fabricate a transition. Invalid/replayed proof or transaction failure must not claim success. If the outcome is uncertain (e.g., lost connection during commit), inspect committed state/audit before retrying.
5. Verify the effective Disabled policy across application instances and normal Local Database administrator admission with all other controls intact. Record independent evidence; retain the original Turnstile configuration and encrypted credentials. Close the management terminal.
6. Once Turnstile recovers, confirm provider health, open the existing Bot Protection workspace, run **Test Turnstile** using the actual browser-issued challenge and exact configured hostname/action/keys, then restore Always via the existing enablement guard. Emergency disable invalidates prior test evidence. Verify Local, LDAP, and browser SSO admission as applicable, fail-closed behavior on invalid challenge, and record restoration/outage duration and audit correlation in the incident.

### Recovery limits and drill

The command's domain transaction has no Redis, Turnstile or external IdP call. Full Flask application bootstrap and deployment management access are not yet qualified under dependency outage. Redis loss can still prevent normal browser admission through existing rate limits; this operation is not a Redis recovery or a bypass of those controls. Independently qualify all-sessions-expired recovery, concurrent attempts, rollback/replay, exact runtime startup and operator access, then repeat drills under the approved operational schedule. No production use before admission and Human Acceptance.
