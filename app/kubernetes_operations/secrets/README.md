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
