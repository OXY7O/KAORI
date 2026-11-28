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

**Recovery dependency:** #4014 and #5416 provide separately scoped source implementations for Bot Protection and Login Protection rollback. Neither is runtime-qualified. Redis outage and targeted-login-spray recovery remain operational qualification scenarios; keep Login Protection activation HOLD until acceptance.


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


## Isolated Login Protection rollback (AL-04, #5416)

This operation is limited to rollback of the optional KAORI-owned Login Protection policy. It is not an emergency login or Redis repair tool. Use only after hosted qualification and explicit incident/change authorization, under the same independent management access and local Super Admin custody prerequisites as BP-03. It does not change the independent Flask-Limiter configuration or clear Redis keys.

### Diagnose before changing policy

- Redis unavailable/misconfigured: keep normal login fail closed; restore the shared Redis service, approved credentials, network/TLS and topology through the infrastructure authority. Do not switch to memory storage, disable rate limits, flush Redis, or edit PostgreSQL manually. Verify both per-IP limiter and identity-budget behavior across instances after recovery.
- Targeted spray: correlate existing credential, lockout and anonymous budget audit with approved edge/network evidence; the identity bucket is pseudonymous and may collide, so do not infer the targeted user from a bucket or an anonymous budget event. Preserve evidence, mitigate malicious traffic at approved infrastructure boundaries, verify trusted-proxy settings and shared store health. Local Super Admin is excluded from durable lockout, not from shared request controls.
- If an incident-approved rollback of the optional policy is necessary and the administrative UI is unavailable, use the scoped command below. Disabling this policy reduces protection for normal local accounts; obtain explicit approval and compensating controls. A rollback cannot restore browser admission while the independent limiter remains unavailable, and a targeted per-IP denial can still persist.

### Governed command

Using the approved interactive management terminal for the exact affected admitted image and correctly selected Compose project:

```bash
docker compose exec -e AUTH_BREAK_GLASS_RECOVERY_ALLOWED=true web flask --app run:app recover-login-protection
```

The authorization flag remains false in persistent configuration. This invocation reads the committed mode/revision, releases the read transaction, then requires the operator to confirm that revision, supply the named operator reference, incident/change reference and non-sensitive reason, acknowledge the rollback and enter current local Super Admin password and unused TOTP via hidden prompts. A competing policy revision change rejects the operation. No browser session is issued.

On success verify the committed Disabled mode, revision, Activity Audit correlation and actor Notification Deck. The revision increases once for a real mode transition; old observation rows remain stored but are no longer authoritative. A fresh-proof repeat on the same current Disabled revision is recorded as unchanged; a stale repeat is rejected. If commit outcome is uncertain, inspect committed evidence before retrying. MFA enrollment, Bot Protection, user lifecycle, existing sessions, provider settings and independent limiter remain intact. No automatic re-enable or recovery CLI activation path is provided.

After infrastructure and attack mitigation, restore the approved protection through the existing policy UI and qualification process: Disabled → Monitor Only → Enforced, with separate authorization, shared Redis probe, recovery evidence and Human Acceptance. Record the protection gap duration and verify ordinary and recovery accounts, Local/LDAP/SSO, existing sessions and generic denial behavior. Qualification requires real Redis outage, all-sessions-expired and targeted-spray drills, PostgreSQL races, audit failure, replay and hosted startup; no production use based on source merge alone.


### Uniform origin/identity budget (AL-05C #5442)

The optional default-off origin/identity guard applies to every credential request before identity lookup, not to a named recovery identity or special route. It is a short-lived request budget, not a durable local account lock. Public targeted spray may still saturate the existing global identity budget or shared NAT/origin budget; do not clear Redis buckets, exempt a recovery username or disable the independent limiter. Restore infrastructure, use the separately authorized isolated management-plane command only when its incident criteria are met, and verify exact recovery evidence. Qualify the candidate cap and trusted proxy/Redis topology in Monitor Only before Enforced. All web instances must use the same configuration; changes begin in Disabled. Existing restricted management-plane custody, MFA, operator attempt limits and independent audit remain necessary.
