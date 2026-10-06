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
