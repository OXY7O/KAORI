# Kubernetes Secret Management

## Purpose

This domain owns explicit live mutations of Kubernetes Secrets. Kubernetes Inventory presents observed snapshots, K8s Governance evaluates posture, and Secret Management validates and executes user-requested changes.

## Current workflows

- guided Secret creation;
- selected-key non-TLS Secret data replacement;
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
- `kubernetes_secrets.rotate_tls`
- `kubernetes_secrets.bulk_rotate_tls`

## Route ownership

- `/kubernetes-operations/secrets` — domain landing page;
- `/kubernetes-operations/secrets/create` — guided create workflow;
- `/kubernetes-operations/secrets/replace` — selected-key non-TLS replacement workflow;
- `/kubernetes-operations/secrets/tls-rotation` — existing TLS rotation workflow.

## Shared layer

Reusable TLS parsing and certificate/private-key validation live in `app/kubernetes/secrets/tls.py`. Low-level Kubernetes Secret payload/client primitives belong under `app/kubernetes/secrets`; orchestration, authorization, feedback, and auditing remain in this domain.

## Workflow boundaries

- Secret creation and Secret data replacement are separate workflows.
- Existing Secret values are never read back or displayed by KAORI.
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

## Protected Secret Reveal recommendation

Protected Secret Reveal is a proposed future workflow and is not active. It must remain separate from Replace Secret Data because a Kubernetes `get` request returns the complete Secret object to the KAORI backend even when the interface intends to display only one selected key. The selected-key limit can reduce browser exposure, but it does not reduce the Kubernetes API credential's ability to read the entire Secret.

Recommended control model:

1. Keep reveal disabled globally and per cluster by default. A cluster must explicitly enable the capability.
2. Add a dedicated `kubernetes_secrets.reveal` permission. Do not grant it automatically to Admin, Editor, Operator, Viewer, or Auditor roles; assign it only through an explicit custom role or super-admin decision.
3. Prefer a dedicated Kubernetes credential for reveal with namespace-scoped `RoleBinding` and the `get` verb only. Do not grant `list` or `watch` on Secrets. Application RBAC must not be the only protection layer.
4. Require step-up authentication immediately before reveal. Local users re-enter their password; SSO users must complete IdP reauthentication or MFA when that capability is available. The elevated session should expire after five minutes.
5. Require an operational reason and ticket/reference number. Production or sensitive clusters should support four-eyes approval with no self-approval.
6. Reveal only one Secret key at a time, masked by default, for a short window such as 15 seconds. Values must never be placed in URLs, server-rendered flash messages, notifications, activity metadata, browser storage, caches, background jobs, or database columns.
7. Serve reveal responses only through HTTPS POST requests with CSRF protection and `Cache-Control: no-store, private`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff`. The response fragment must be removed from the DOM after the reveal window.
8. Do not preload, cache, or persist the Kubernetes response. Select the requested key in request memory, return only that value, and discard the complete Secret object immediately.
9. Record `requested`, `approved`, `revealed`, `denied`, and optional `copied` activity events using safe metadata only: actor, approver, cluster, namespace, Secret name, key name, reason, ticket, timestamp, source IP, and outcome. Never record the value or its hash.
10. Rate-limit reveal attempts and alert on repeated access, cross-namespace access, or access outside an approved window.
11. Keep high-risk keys unavailable in the UI by default: service-account tokens, `tls.key`, and SSH private keys. TLS and SSH should continue to use rotation workflows and metadata/fingerprint verification rather than plaintext reveal.
12. Require Kubernetes Secrets encryption at rest and Kubernetes audit logging at Metadata level before enabling reveal for a cluster. Request or RequestResponse audit levels must not capture Secret bodies.

Recommended user flow:

- Select cluster, namespace, Secret, and one key from inventory metadata.
- Enter reason and ticket.
- Complete step-up authentication.
- Obtain approval when the cluster policy requires it.
- Press and hold **Reveal for 15 seconds**.
- KAORI performs one live Kubernetes `get`, extracts only the selected key in memory, renders a no-store response, auto-hides it, and records a value-free audit event.

This capability should be implemented as a dedicated `Protected Reveal` page or modal, not embedded directly into the Replace form. Replace must continue to work without reading existing data. For longer-term maturity, integrate KAORI with an external secret manager such as Vault or a cloud secret manager so controlled retrieval and rotation use the source of truth instead of Kubernetes Secrets as the primary credential store.
