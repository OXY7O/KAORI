# Kubernetes API Compatibility

KAORI uses one readable API contract identifier, `kubernetes-api-v1`. The identifier is a KAORI contract version, not a Kubernetes runtime version.

## Validation model

Every cluster validation and inventory sync performs live discovery before selecting an API adapter:

1. Detect the Kubernetes runtime version and lifecycle (`current`, `legacy`, or `unknown`).
2. Discover served API groups, versions, resources, and API-supported verbs.
3. Check the kubeconfig authorization through `SelfSubjectAccessReview` when available.
4. Select the stable API first.
5. Select a tested legacy adapter only when the stable API is unavailable and the legacy API is actually served and authorized.
6. Persist feature-level evidence in `clusters.kubernetes_api_discovery_summary`.

Lifecycle is context and warning posture. It is not a global switch that blindly changes every request to a beta API.

## Adapter policy

Current explicit fallbacks:

- Ingress: `networking.k8s.io/v1` -> `networking.k8s.io/v1beta1` -> `extensions/v1beta1`.
- CronJob: `batch/v1` -> `batch/v1beta1`.

Core resources such as Secret, ConfigMap, Pod, Service, Namespace, and Node use `core/v1`; they do not have a beta fallback. When Secret access is not authorized, KAORI preserves the last Secret inventory snapshot and continues syncing permitted resource types instead of treating the condition as an API-version mismatch.

## Maintenance rule

A new legacy fallback must include discovery candidates, a normalized collector adapter, tests against representative payloads, deprecation metadata, and documentation. Do not add version-number conditionals directly inside feature routes or templates.

## Generated client contract

The pinned Kubernetes Python client uses `response_types_map` for low-level
`ApiClient.call_api()` deserialization. Do not pass the legacy `response_type`
keyword. Live API services should narrow generated response unions to the expected
model before reading `items`, `data`, or `metadata`.

## Integration workspace

The Kubernetes integration UI is organized into Connection & Contract, Compatibility & Capabilities, Runtime & History, and Inventory & Lifecycle domains. The registry and detail workspace opt into the KAORI semantic color contract. Deleting a Kubernetes connection requires `clusters.manage`, opens a KAORI Violet confirmation modal, uses the existing cluster lifecycle service, and records success or failure through persistent notification and Activity Audit Log.
