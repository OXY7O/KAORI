# Secret Reveal Settings

This Settings domain owns governance configuration for Protected Kubernetes Secret Reveal. It does not read Secret values and does not execute reveal requests.

## Hierarchy

```text
Cluster
└── Namespace
    └── Disabled | Step-up authentication | Approval required
```

Cluster-level fields are limited to security readiness attestations:

- Kubernetes Secret encryption at rest verified;
- Kubernetes audit logging at Metadata level verified.

Namespace policy is explicit and default-deny. No policy row means Reveal is disabled. The Add/Edit Cluster form must not contain Reveal controls.

## Ownership

- `app/kubernetes_operations/secrets/reveal_policy.py`: canonical policy and readiness rules.
- `app/settings/secret_reveal/service.py`: Settings page context and summaries.
- `app/settings/secret_reveal/routes.py`: RBAC, CSRF, activity, toast, and save actions.
- `app/templates/settings/secret_reveal/index.html`: cluster selector, readiness controls, and namespace policy table.
- `secret_reveal_namespace_policies`: one unique policy per cluster and namespace.

Every save action emits a toast/notification and Operational Activity record containing only cluster, namespace, readiness, policy, and outcome. It must never contain kubeconfig or Secret data.

## Security rules

- Permission: `kubernetes_secrets.manage_reveal`.
- `clusters.manage` does not grant access to this page.
- A namespace cannot be enabled before both cluster readiness attestations are true.
- New access cannot be granted to a namespace missing from the latest inventory snapshot.
- Disabling cluster readiness immediately expires pending/approved requests and suspends all namespace policies without deleting them.
- Changing or disabling a namespace policy expires pending/approved requests for that namespace.
- The global environment switch remains outside the database and is displayed read-only.
