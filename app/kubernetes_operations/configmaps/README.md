# ConfigMap Management

## Purpose

`ConfigMap Management` is the KAORI operational domain for creating, reading, updating, and deleting Kubernetes ConfigMaps. It is separate from Configuration Inventory: inventory provides snapshot visibility, while this domain performs controlled live Kubernetes operations.

## Navigation

The sidebar exposes one entry only:

```text
K8s Operations
└── ConfigMap Management
```

The landing page owns three permission-aware workflow cards:

- Create ConfigMap
- View & Update ConfigMap
- Delete ConfigMap

Do not add separate sidebar entries for these actions.

## Security boundary

ConfigMap values may be read and displayed because ConfigMaps are non-secret configuration. They must still be treated as operationally sensitive because they can expose topology, endpoints, feature flags, or accidentally stored credentials.

- Use the cluster's primary kubeconfig.
- Kubernetes administrators must scope ConfigMap permissions by namespace through Role/RoleBinding where possible.
- KAORI permissions are separate: `view`, `create`, `update`, and `delete`.
- Delete is destructive and must remain a dedicated permission.
- Activity and notification metadata stores key names and change counts, never full values.
- Every create, update, and delete apply repeats Kubernetes server-side dry-run immediately before the real operation.

## Create contract

- Cluster selector shows the cluster name only.
- Namespace options come from the selected cluster inventory snapshot.
- Supports text `data` and base64-entered `binaryData`.
- Validates Kubernetes names, key syntax, duplicate keys, namespace ownership, and the 1 MiB object limit.
- Create-only: HTTP 409 never overwrites an existing ConfigMap.
- Immutable may be selected during creation.

## Update contract

Existing values are read live from Kubernetes and displayed in the editor.

Two modes are supported:

1. **Merge selected keys** — default. Submitted keys are added or changed; omitted keys remain on the server.
2. **Replace all data** — advanced. Omitted keys are removed and explicit confirmation is required.

Blank text is a valid empty string. Removing a row only removes the key in Replace mode; Merge mode preserves omitted keys.

Before apply, KAORI calculates added, changed, removed, and unchanged key names. Full values are not written to logs or notifications. Immutable ConfigMaps cannot be updated.

## Impact context

Impact context is built from `PodInventory.configuration_references` and deduplicated to workload identity. The UI warns that:

- environment variables require Pod recreation;
- mounted files may update eventually;
- applications may not reload automatically;
- `subPath` consumers do not receive live volume updates.

Restart remains a separate future action and permission.

## Delete contract

- Load impact context before deletion.
- User must type the exact ConfigMap name.
- Validate deletion with dry-run first.
- Apply repeats dry-run before actual deletion.
- Deletion does not restart or repair dependent workloads.

## Activity events

- `kubernetes_configmap_validated`
- `kubernetes_configmap_validation_failed`
- `kubernetes_configmap_created`
- `kubernetes_configmap_creation_failed`
- `kubernetes_configmap_update_validated`
- `kubernetes_configmap_updated`
- `kubernetes_configmap_update_failed`
- `kubernetes_configmap_delete_validated`
- `kubernetes_configmap_deleted`
- `kubernetes_configmap_delete_failed`

Safe metadata includes cluster, namespace, ConfigMap name, operation, key names, diff key lists, impact count, and resource version. Never store submitted or existing values.
