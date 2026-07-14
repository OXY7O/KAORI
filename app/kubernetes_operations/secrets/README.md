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
- Existing Secret values remain unread by Create and Replace. Protected Reveal is the only explicit read path and is isolated behind separate policy, credentials, permissions, reauthentication, and audit controls.
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

### Enablement gates

Reveal is default-deny at every layer:

1. Global configuration `KUBERNETES_SECRET_REVEAL_ENABLED=true` must be set explicitly.
2. The target cluster must use `secret_reveal_policy=step_up` or `approval_required`.
3. The cluster must have a dedicated reveal kubeconfig that targets the same Kubernetes API server as its primary kubeconfig.
4. Encryption at rest and Kubernetes audit logging at Metadata level must both be marked verified for the cluster.
5. The user must hold `kubernetes_secrets.reveal`; approval decisions require `kubernetes_secrets.approve_reveal`.
6. Cluster policy, prerequisite attestations, and the dedicated kubeconfig require `kubernetes_secrets.manage_reveal`; `clusters.manage` alone cannot alter these controls.
7. `kubernetes_secrets.reveal` is not assigned to any built-in role by default. Admin receives approval and policy-management permissions but not reveal permission; Super Admin still has the explicit platform bypass defined by the RBAC model.

The dedicated Kubernetes credential should be namespace-scoped and grant `get` on Secrets only. Do not grant `list` or `watch`. KAORI validates that the kubeconfig points to the same API server, but Kubernetes RBAC remains the authoritative resource boundary.

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
- Step-up clusters create an immediately approved request with a short expiry.
- Approval-required clusters create a pending request. Requestor and approver must be different users.
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
- reads through the dedicated reveal kubeconfig;
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

- `reveal_service.py` owns policy/readiness validation, request lifecycle, approval state, expiry, live Kubernetes read, one-time consumption, decoding, and safe metadata.
- `SecretRevealRequest` stores workflow state only; it has no payload/value column.
- route handlers own RBAC, reauthentication session state, rate limiting, toast/notification feedback, and activity records.
- `templates/kubernetes_operations/secrets/reveal.html` owns request, approval, and one-time display surfaces.
- cluster registration/edit owns per-cluster policy, dedicated kubeconfig replacement/revocation, and prerequisite attestations.

Replace Secret Data remains the preferred update path when the operator already knows the intended replacement value. Protected Reveal is an exceptional read path, not a convenience default.
