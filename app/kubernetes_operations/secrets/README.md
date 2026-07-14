# Kubernetes Secret Management

## Purpose

This domain owns explicit live mutations of Kubernetes Secrets. Kubernetes Inventory presents observed snapshots, K8s Governance evaluates posture, and Secret Management validates and executes user-requested changes.

## Current workflows

- guided Secret creation;
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
- `kubernetes_secrets.rotate_tls`
- `kubernetes_secrets.bulk_rotate_tls`

## Route ownership

- `/kubernetes-operations/secrets` — domain landing page;
- `/kubernetes-operations/secrets/create` — guided create workflow;
- `/kubernetes-operations/secrets/tls-rotation` — existing TLS rotation workflow.

## Shared layer

Reusable TLS parsing and certificate/private-key validation live in `app/kubernetes/secrets/tls.py`. Low-level Kubernetes Secret payload/client primitives belong under `app/kubernetes/secrets`; orchestration, authorization, feedback, and auditing remain in this domain.

## Workflow boundaries

- Secret creation and Secret data replacement are separate workflows.
- Existing Secret values are never read back or displayed by KAORI.
- TLS uses a dedicated rotation workflow because certificate/private-key matching, SAN coverage, and Governance linkage require specialized validation.
- Non-TLS replacement is a planned controlled workflow for Opaque, Basic Auth, Registry, and SSH Secrets. It must require users to submit complete replacement material rather than editing revealed values.
- ConfigMap operations belong to a separate `ConfigMap Management` operational domain. ConfigMap and Secret inventory may remain under Configuration Inventory while mutation workflows stay separate because their sensitivity and validation rules differ.

## Landing-page data

Secret Management overview metrics and type distribution are read from the latest `ConfigurationInventory` database snapshot. The landing page must not call the live Kubernetes API. Live API access is reserved for explicit validation and mutation actions.

## Landing-page presentation

The Secret Management landing page is action-oriented. It must prioritize operational workflows and security boundaries rather than inventory analytics or Secret-type distribution charts.

The workflow cards are:

- **Create Secret** — active workflow for Opaque, Basic Auth, TLS, Registry, and SSH Secret creation;
- **Replace Secret Data** — visible placeholder for the planned non-TLS replacement workflow;
- **TLS Rotation** — active specialized workflow for existing TLS Secrets.

A placeholder must never imply that an unavailable operation already works. Planned workflows use a disabled action, a clear `Coming soon` status, and an explicit description of their future scope.

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
