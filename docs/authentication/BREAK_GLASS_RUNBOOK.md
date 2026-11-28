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

**Unresolved recovery dependency:** #4014 remains open for an isolated operator operation when all administrator sessions have expired and Turnstile is unavailable. An equivalent Redis outage and targeted-login-spray scenario must also be qualified. No independently executable management operation, public bypass or default direct database-edit procedure is claimed here. Keep activation HOLD until that dependency is resolved.
