# Kubernetes Secret Management

## Purpose

This domain owns explicit live mutations of Kubernetes Secrets. Kubernetes Inventory presents observed snapshots, K8s Governance evaluates posture, and Secret Management validates and executes user-requested changes.

## Current workflows

- guided Secret creation;
- selected-key non-TLS Secret data replacement;
- protected one-time Secret key reveal;
- single TLS Secret rotation;
- bulk TLS Secret rotation;
- centralized validation, notification, and operational audit.

## Supported create types

- Generic / `Opaque`;
- `kubernetes.io/basic-auth`;
- `kubernetes.io/tls`;
- `kubernetes.io/dockerconfigjson`;
- `kubernetes.io/ssh-auth`.

## Mandatory rules

1. Validate with Kubernetes server-side dry-run before mutation.
2. Never persist plaintext Secret values, passwords, tokens, certificate private keys, SSH private keys, or raw Docker credentials.
3. Never include sensitive payloads in notification metadata, activity audit records, exception messages, Celery arguments, or application logs.
4. Keep create and update/rotation workflows distinct. Creation must never silently overwrite an existing Secret.
5. Use synchronous request-memory handling for Secret material; do not serialize credentials into Celery or Redis.
6. Record only safe target identity and result metadata: cluster, namespace, Secret name/type, key names, immutable state, actor, outcome, and Kubernetes UID/resource version when available.
7. Use dedicated RBAC permissions rather than a broad cluster-management permission.
8. Reconcile the affected inventory record after a successful mutation. Until targeted reconciliation is implemented, the next inventory sync remains the authoritative reconciliation path.

## Permissions

- `kubernetes_secrets.view`
- `kubernetes_secrets.create`
- `kubernetes_secrets.replace`
- `kubernetes_secrets.reveal`
- `kubernetes_secrets.approve_reveal`
- `kubernetes_secrets.manage_reveal`
- `kubernetes_secrets.rotate_tls`
- `kubernetes_secrets.bulk_rotate_tls`

## Route ownership

- `/kubernetes-operations/secrets` — domain landing page;
- `/kubernetes-operations/secrets/create` — guided create workflow;
- `/kubernetes-operations/secrets/replace` — selected-key non-TLS replacement workflow;
- `/kubernetes-operations/secrets/reveal` — protected request, approval, reauthentication, and one-time reveal workflow;
- `/kubernetes-operations/secrets/tls-rotation` — existing TLS rotation workflow.

## Shared layer

Reusable TLS parsing and certificate/private-key validation live in `app/kubernetes/secrets/tls.py`. Low-level Kubernetes Secret payload/client primitives belong under `app/kubernetes/secrets`; orchestration, authorization, feedback, and auditing remain in this domain.

## Workflow boundaries

- Secret creation and Secret data replacement are separate workflows.
- Existing Secret values remain unread by Create and Replace. Protected Reveal is the only explicit read path and is isolated behind cluster readiness, namespace policy, KAORI permissions, reauthentication, optional approval, rate limiting, and audit controls.
- TLS uses a dedicated rotation workflow because certificate/private-key matching, SAN coverage, and Governance linkage require specialized validation.
- Non-TLS replacement is an active controlled workflow for Opaque, Basic Auth, Registry, and SSH Secrets. Existing values remain unread and hidden; only submitted keys are patched.
- ConfigMap operations belong to a separate `ConfigMap Management` operational domain. ConfigMap and Secret inventory may remain under Configuration Inventory while mutation workflows stay separate because their sensitivity and validation rules differ.

## Landing-page data

Secret Management overview metrics and type distribution are read from the latest `ConfigurationInventory` database snapshot. The landing page must not call the live Kubernetes API. Live API access is reserved for explicit validation and mutation actions.

## Landing-page presentation

The Secret Management landing page is action-oriented. It must prioritize operational workflows and security boundaries rather than inventory analytics or Secret-type distribution charts.

The workflow cards are:

- **Create Secret** — active workflow for Opaque, Basic Auth, TLS, Registry, and SSH Secret creation;
- **Replace Secret Data** — active selected-key patch workflow for supported mutable non-TLS Secrets;
- **Protected Secret Reveal** — active default-deny one-key read workflow for explicitly authorized users and verified clusters;
- **TLS Rotation** — active specialized workflow for existing TLS Secrets.

Unavailable operations must never appear active. The Replace card is enabled only for users with `kubernetes_secrets.replace`; other users see a restricted action.

The landing page may use compact snapshot totals in the hero, but must not add decorative charts unless they directly help the user choose or execute an operation.

## Create Secret interaction contract

The Create Kubernetes Secret page follows these maintenance rules:

- cluster options display only the registered cluster name; environment labels are not part of target selection;
- namespace is a controlled dropdown loaded from the latest `NamespaceInventory` snapshot for the selected cluster through `kubernetes_operations.secret_namespace_options`;
- server-side validation rechecks that the submitted namespace belongs to the selected cluster snapshot, so manually altered requests cannot target an unrelated namespace;
- Secret type cards use stable type-specific tones: blue for Opaque, violet for Basic Auth, emerald for TLS, cyan for Registry, and amber for SSH;
- the Secret content section inherits the selected type tone while retaining type-specific fields and validation;
- page-specific Secret type styling is isolated through the `page_styles` layout block rather than being mixed into global dashboard CSS;
- Validate and Create use HTMX multipart submissions so passwords, key-value entries, and selected files remain in the browser while the result area and operational toast are updated;
- every Validate/Create attempt reaches server-side validation and every success or failure creates a toast, operational activity entry, and notification using only safe metadata;
- plaintext values, passwords, tokens, certificate private keys, SSH private keys, Docker auth payloads, and upload contents must never be copied into activity metadata or notification text.

## Create validation boundaries

Before calling the Kubernetes API, KAORI validates:

- registered cluster identity;
- namespace membership in the selected cluster inventory;
- DNS-compatible Secret and namespace names;
- supported Secret type and mutability value;
- Opaque key syntax and duplicate keys;
- Basic Auth password confirmation;
- TLS certificate/private-key parsing, matching, expiry, UTF-8 encoding, and upload size;
- Registry server, required credential fields, and optional email format;
- unencrypted PEM/OpenSSH private-key parsing;
- the Kubernetes 1 MiB Secret payload limit.

Kubernetes API responses are converted to user-facing outcomes for duplicate resources, missing namespaces, invalid payloads, authorization failures, authentication failures, invalid kubeconfig, and connectivity failures. Existing Secrets remain protected by create-only API semantics and are never overwritten.


## Replace Secret Data contract

The replacement workflow uses the latest `ConfigurationInventory` snapshot only for cluster, namespace, Secret identity, type, immutability, and observed key names. It must not call `read_namespaced_secret`, deserialize current Secret data, or reveal existing values in the browser.

Replacement semantics:

- `********` is a placeholder only and is never submitted as a Secret value;
- a blank existing-key field omits that key from the Kubernetes patch, preserving its current server value;
- blank is reserved for preserve semantics, so this workflow does not write an empty-string value; a future clear-value action must use an explicit separate control;
- a populated field replaces only the submitted key;
- Opaque replacement may patch observed keys and add new keys, but does not delete keys;
- Basic Auth can replace username and password independently; password confirmation is required when password changes;
- Container Registry is atomic because `.dockerconfigjson` is one payload: when any registry field changes, server, username, and password/token must all be submitted as a complete replacement bundle;
- SSH replacement submits one complete private key through upload or paste; blank input is a no-op;
- TLS Secrets remain excluded and use the dedicated TLS Rotation workflow;
- immutable Secrets are visible as immutable targets but cannot be selected or patched.

Every Apply request runs Kubernetes server-side dry-run immediately before the real patch. The patch contains only submitted keys, and the Kubernetes response body is not preloaded so KAORI does not deserialize Secret data returned by the API.

Validate and Replace attempts always generate an operational toast, notification, and activity record. Safe metadata may include target identity, Secret type, operation, updated key names/count, and `existing_values_read=false`. Values, passwords, tokens, registry payloads, and private keys must never enter logs, activity metadata, notifications, or background jobs.

The default Editor and Admin roles receive `kubernetes_secrets.replace`. Existing installations must run `flask seed-rbac` after applying this change so the permission catalog and built-in role assignments are synchronized.

Implementation ownership:

- `replace_service.py` owns inventory target lookup, Kubernetes dry-run/patch execution, API error mapping, and safe operation metadata;
- `replace_payloads.py` owns type-specific input validation and construction of the selected-key patch payload;
- route handlers own RBAC, toast/notification feedback, and operational activity recording.

## Protected Secret Reveal contract

Protected Secret Reveal is active as a separate security-sensitive workflow. It must never be merged into Replace Secret Data because Kubernetes `get Secret` returns the complete Secret object to the KAORI backend even when the browser receives only one selected key.

### Single-kubeconfig architecture

Protected Secret Reveal uses the same kubeconfig stored on the cluster registration. KAORI does not store or select a second reveal credential. The Kubernetes cluster administrator owns the ServiceAccount/user and Role/RoleBinding design for that identity. Its permissions should be the union of only the KAORI capabilities intentionally enabled for that cluster, with namespace scope preferred over cluster-wide access.

Application controls remain mandatory defense in depth: `kubernetes_secrets.reveal`, optional separation-of-duties approval, step-up authentication, reason and ticket, rate limiting, one-time consumption, no-cache responses, and payload-free activity records. This reduces credential sprawl, but the cluster identity has a larger blast radius than separate per-function credentials; review and rotate the kubeconfig whenever its Kubernetes RBAC scope changes.

When migrating from the earlier dedicated-reveal-credential model, dropping the database column does not revoke the old Kubernetes credential. The Kubernetes administrator must delete or revoke the obsolete ServiceAccount token/client credential and remove its RoleBinding separately.

### Enablement gates

Reveal is default-deny at every layer:

1. Global configuration `KUBERNETES_SECRET_REVEAL_ENABLED=true` must be set explicitly.
2. The target namespace must have an explicit `step_up` or `approval_required` policy under **Settings > Secret Reveal**. Missing policy records are disabled by default.
3. The cluster must have its normal kubeconfig registered, and the Kubernetes administrator must authorize that identity to `get` only the intended Secrets within the intended namespaces.
4. Encryption at rest and Kubernetes audit logging at Metadata level must both be marked verified for the cluster.
5. The user must hold `kubernetes_secrets.reveal`; approval decisions require `kubernetes_secrets.approve_reveal`.
6. Cluster readiness attestations and namespace policies require `kubernetes_secrets.manage_reveal`; `clusters.manage` alone cannot alter these controls.
7. `kubernetes_secrets.reveal` is not assigned to any built-in role by default. Admin receives approval and policy-management permissions but not reveal permission; Super Admin still has the explicit platform bypass defined by the RBAC model.

The cluster kubeconfig identity should be namespace-scoped where possible. For Secret reveal, grant `get` only within the intended scope and avoid `list` or `watch`. The same identity may also carry verbs required by other enabled KAORI operations, so Kubernetes RBAC remains the authoritative resource boundary and must be reviewed as a union of explicitly enabled capabilities.


### Namespace policy ownership

Reveal authorization follows a strict hierarchy:

```text
Global feature switch
→ Cluster readiness attestations
→ Explicit namespace policy
→ KAORI user permission
→ Step-up / approval
→ Kubernetes RBAC
```

Namespace policy records are stored in `secret_reveal_namespace_policies` with a unique `(cluster_id, namespace)` boundary. There is no implicit all-namespace policy and migration does not copy the former cluster-wide policy, so upgrades return to default-deny until namespaces are explicitly enabled. Changing or disabling a namespace policy expires active requests for that namespace; disabling cluster readiness expires all active requests for the cluster.

The Settings page lists namespaces from the latest `NamespaceInventory` snapshot. A removed namespace policy can still be disabled even if its snapshot is stale, but new access cannot be granted to a namespace missing from inventory.

### Supported and blocked values

Reveal supports one key from:

- `Opaque`;
- `kubernetes.io/basic-auth`;
- `kubernetes.io/dockerconfigjson`.

The following remain blocked:

- `kubernetes.io/service-account-token`;
- `kubernetes.io/tls` and `tls.key`;
- `kubernetes.io/ssh-auth` and `ssh-privatekey`.

TLS and SSH private-key material must use rotation and fingerprint workflows instead of plaintext display.

### Request lifecycle

- A request stores target identity, selected key name, policy, reason, ticket, requestor, approver, status, and expiry only.
- Step-up namespaces create an immediately approved request with a short expiry.
- Approval-required namespaces create a pending request. Requestor and approver must be different users.
- Approval creates a short one-time window. Denial closes the request.
- Duplicate active requests for the same requestor/cluster/namespace/Secret/key are rejected.
- Approved requests are consumed after one successful reveal and cannot be reused.
- Pending and approved records automatically become expired when their expiry is reached.

### Reauthentication

Database-managed users must re-enter their current KAORI password. The elevated session is bound to the authenticated user and expires according to `KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS`.

External IdP step-up is intentionally blocked until LDAP/SSO reauthentication or MFA integration exists. A controlled database break-glass account is the temporary supported path. Logout clears the elevated reveal session.

### Live read boundary

The live endpoint:

- accepts HTTPS POST only in production;
- is CSRF protected;
- is rate-limited per authenticated user;
- reads through the cluster kubeconfig identity;
- retrieves the Secret once, selects the approved key in request memory, and clears references to the complete data map;
- rejects values larger than `KUBERNETES_SECRET_REVEAL_MAX_BYTES`;
- returns UTF-8 text when safe, otherwise base64 representation;
- sets `Cache-Control: no-store, private`, `Pragma: no-cache`, `Expires: 0`, and `X-Content-Type-Options: nosniff`;
- disables HTMX history snapshots for the output container;
- removes the rendered value from the DOM after `KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS`;
- never provides a persistent copy button.

Python cannot guarantee physical zeroization of immutable memory, so the implementation minimizes object lifetime and clears mutable dictionaries immediately after extracting the selected key. The Secret value, hash, prefix, and length are never persisted or logged.

### Audit and notification events

The workflow emits safe activity/notification events for:

- request submitted or failed;
- request approved, denied, or decision failed;
- reauthentication success or failure;
- reveal success or failure;
- rate limiting.

Safe metadata includes actor IDs, target identity, selected key name, policy, reason, ticket, request status, source IP, and outcome. It explicitly records `secret_value_recorded=false` and must never include value-derived data.

### Configuration

```text
KUBERNETES_SECRET_REVEAL_ENABLED=false
KUBERNETES_SECRET_REVEAL_RATE_LIMIT=3 per 5 minutes
KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS=300
KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS=15
KUBERNETES_SECRET_REVEAL_MAX_BYTES=65536
KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES=10
KUBERNETES_SECRET_REVEAL_PENDING_TTL_HOURS=24
```

### Implementation ownership

- `reveal_policy.py` owns namespace-scoped policy validation, cluster readiness, and policy persistence.
- `reveal_service.py` owns request lifecycle, approval state, expiry, live Kubernetes read, one-time consumption, decoding, and safe metadata.
- `SecretRevealRequest` stores workflow state only; it has no payload/value column.
- route handlers own RBAC, reauthentication session state, rate limiting, toast/notification feedback, and activity records.
- `templates/kubernetes_operations/secrets/reveal.html` owns request, approval, and one-time display surfaces.
- cluster registration owns the single kubeconfig identity only. **Settings > Secret Reveal** owns cluster readiness attestations and explicit namespace policies.

Replace Secret Data remains the preferred update path when the operator already knows the intended replacement value. Protected Reveal is an exceptional read path, not a convenience default.

## Navigation consolidation

The sidebar exposes one operational Secret entry only: **K8s Operations > Secret Management**. Create, Replace, Protected Reveal, and TLS Rotation remain separate route-level workflows, but users enter them through permission-aware cards on the Secret Management landing page. Reveal governance is configured separately under **Settings > Secret Reveal**. Do not add operational workflows back as sibling sidebar items.

The Secret Management landing route accepts any Secret operation permission so a user who can create, replace, reveal, approve, or rotate can still reach the card workspace even without the inventory-only `kubernetes_secrets.view` permission. Cards remain visible as a capability map, but unavailable actions render as restricted and cannot link to protected endpoints.

Welcome uses the same consolidated destination. Every Secret-related permission resolves to `kubernetes_operations.secret_management`, preventing role-dependent shortcuts from bypassing the domain landing page.

## Protected Reveal CSRF contract

Protected Reveal uses hand-written POST forms instead of `FlaskForm`. `app/__init__.py` injects `flask_wtf.csrf.generate_csrf` into Jinja as `csrf_token`, and every Reveal POST route explicitly calls `validate_csrf` before reading credentials, saving a decision, or contacting Kubernetes.

A missing, invalid, or expired token must:

- reject the operation before any Secret read or state mutation;
- create a controlled error toast and operational activity record;
- avoid logging the submitted password or any Secret-derived value;
- instruct the user to refresh the page and retry.

This scoped implementation must not be replaced with global `CSRFProtect` activation without first auditing every existing POST and HTMX form in KAORI.

## Manual test scenarios

Run these scenarios in a non-production namespace before enabling Protected Reveal for production.

### A. Navigation and permission cards

1. Sign in with a role that has only `kubernetes_secrets.create`.
2. Confirm the sidebar shows only **Secret Management** under K8s Operations.
3. Open Secret Management and confirm Create is active while Replace, Reveal, and TLS Rotation are restricted.
4. Repeat with replace-only, reveal-only, approver-only, rotate-only, and bulk-rotate-only roles.
5. Confirm direct protected URLs still return 403 when the required route permission is absent.

### B. CSRF rendering and rejection

1. Open `/kubernetes-operations/secrets/reveal` and confirm the page renders without `csrf_token is undefined`.
2. Inspect each Reveal POST form and confirm a non-empty hidden `csrf_token` exists.
3. Submit a valid form normally and confirm it reaches the expected workflow.
4. Remove or alter the token in browser developer tools and submit again.
5. Confirm KAORI rejects the request, shows an error toast, records a failed activity event, and performs no approval, reauthentication, or Kubernetes read.

### C. Global, cluster-readiness, and namespace-policy gates

1. Set `KUBERNETES_SECRET_REVEAL_ENABLED=false`; confirm the page displays the global-disabled state and target controls cannot be used.
2. Enable the global switch but leave every namespace Disabled in **Settings > Secret Reveal**; confirm the cluster is not selectable.
3. Try enabling a namespace before encryption/audit attestations are verified; confirm saving is rejected.
4. Verify both cluster prerequisites, enable one namespace as Step-up, and confirm only that namespace is selectable.
5. Enable another namespace as Approval Required and confirm each namespace follows its own policy.

### D. Kubernetes RBAC outcomes

Using the single cluster kubeconfig identity:

1. Without `get` on Secret, submit an approved reveal and confirm a controlled 403 message, toast, and failed activity record.
2. With `get` scoped to one namespace, confirm reveal succeeds only in that namespace.
3. Attempt another namespace and confirm Kubernetes denies it.
4. Use an invalid/expired credential and confirm a controlled authentication error.
5. Use an unavailable API endpoint and confirm a connectivity error without traceback exposure.

### E. Step-up workflow

1. Submit a Step-up request with a valid reason and ticket.
2. Attempt Reveal before reauthentication; confirm it is blocked.
3. Enter an incorrect KAORI password; confirm failure toast/activity and no elevated session.
4. Enter the correct password; confirm the short elevated session becomes active.
5. Reveal once and confirm the request status becomes Revealed.
6. Attempt to reveal the same request again; confirm it is rejected.
7. Wait beyond `KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS`; confirm a new approved request requires reauthentication again.

### F. Approval-required workflow

1. User A submits a request.
2. Confirm User A cannot approve or deny their own request.
3. User B with `kubernetes_secrets.approve_reveal` approves it.
4. Confirm User A receives a notification and can reveal only after reauthentication.
5. Repeat with denial and confirm no reveal action becomes available.
6. Let an approved request pass its expiry and confirm it cannot be consumed.

### G. Secret-type and key restrictions

1. Confirm Opaque, Basic Auth, and Registry key names can be requested.
2. Confirm ServiceAccount token Secrets are blocked.
3. Confirm TLS and SSH private-key Secrets are blocked.
4. Attempt to alter `key_name`, `inventory_id`, cluster, or namespace in the request and confirm server-side validation rejects the mismatch.
5. Confirm only one selected key is rendered to the browser.

### H. Value handling and browser behavior

1. Reveal a normal UTF-8 value and confirm it disappears after the configured window.
2. Reveal binary data and confirm the safe base64 representation path works.
3. Confirm browser back/forward history does not restore the value.
4. Confirm response headers contain `Cache-Control: no-store, private`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff`.
5. Search application logs, database activity metadata, notification payloads, Redis, and browser storage for the revealed value; no match is permitted.

### I. Rate limiting and concurrent consumption

1. Exceed the configured request/reveal rate limit and confirm a controlled rate-limit response and activity event.
2. Send two concurrent Reveal POSTs for the same approved request.
3. Confirm PostgreSQL row locking permits only one successful consumption.
4. Confirm the second request reports that the approval has already been consumed.

### J. Toast, notification, and activity coverage

Verify feedback for request success/failure, reauthentication success/failure, approval, denial, reveal success/failure, CSRF failure, Kubernetes RBAC failure, expiry, and rate limiting. Activity metadata may contain target identity, actor, key name, reason, ticket, policy, and outcome, but never Secret value, value hash, prefix, length, password, token, or kubeconfig content.

## Landing card CSS reliability

Secret Management workflow cards must use color utilities already present in the compiled Tailwind output. A card must not introduce a new palette only through a Jinja template unless the CSS build is also regenerated and verified. Missing generated utilities can leave icon containers and primary actions white while a generic border renders as a hard dark outline.

The Protected Secret Reveal card uses the established emerald palette and stable Lucide icons (`shield-check`, `eye`, and `settings`). Its primary action is a solid emerald button, while namespace-policy management remains a neutral secondary action. When changing card colors, verify the required background, border, text, gradient, and dark-mode classes in `app/static/css/output.css` before delivery.

## Reveal request action visibility

The `Reveal once` action is rendered only while a request is `approved`. An active step-up session does not revive an `expired`, `denied`, or already `revealed` request. Expired rows must provide a `Create new request` action that restores the same cluster, namespace, Secret, and key selection so the user can submit a fresh audited request. Approved rows should show their expiry timestamp to make the short validity window explicit.

## Real-time approval status and notifications

Protected Secret Reveal approval uses notification-driven and polling-based status updates:

- A pending `approval_required` request creates a notification for every active user who has `kubernetes_secrets.approve_reveal`, excluding the requester.
- Approval and denial create a requester notification with a direct action back to Protected Secret Reveal.
- The request and approval panels poll `/kubernetes-operations/secrets/reveal/status` every four seconds through HTMX.
- When an approver changes a request to `approved` or `denied`, the requester row updates without a full-page refresh.
- An approved row displays `Reveal once` immediately when the requester's step-up session is active; otherwise it displays `Reauthenticate first`.
- The same status poll refreshes the notification-center badge out-of-band without exposing Secret values.
- Polling responses contain request metadata only. Secret values remain restricted to the one-time no-store reveal response.

## Real-time approval UI boundary

The Secret Reveal status poll updates only `#secret-reveal-request-status`. It must
not embed the navigation Notification Center as a nested OOB fragment, because a
repeating HTMX response can duplicate the notification trigger outside the navbar.
The canonical `#notification-center` owns its own `/notifications/panel` polling and
replaces itself in place. Keep these two polling boundaries independent.

## Protected Reveal layout and request pagination

- The one-time value card uses a neutral surface without a hard border. Sensitive emphasis is limited to the badge and value surface.
- `Security boundary` and `My reveal requests` are paired in one responsive two-column row. The security card explains the request flow using a vertical dot-and-line sequence.
- `My reveal requests` is paginated server-side with 5, 10, or 25 rows. HTMX polling preserves the selected page and page size.
- Pending approvals remain below the paired cards and continue to refresh through the same status boundary.
