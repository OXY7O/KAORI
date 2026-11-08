# Kubernetes Tenant Native Provider

Issue #120 makes Native Kubernetes the baseline Tenant Management provider. A supported cluster does not require Capsule to provision and reconcile the baseline Tenant lifecycle.

## Authority

Native provider operations are permitted only while the Tenant committed authority is native_kubernetes with provider state native. Native reconciliation never races a Tenant whose authority is Capsule. Provider transfer and recovery remain explicit state transitions.

## Capability matrix

Full Kubernetes Validation records optional Tenant mutation capabilities in the canonical KubernetesConnection discovery summary. The Native provider normalizes those observations into the common statuses: available, degraded, unavailable, and not_applicable.

The capability matrix covers Namespace, ResourceQuota, LimitRange, namespaced RBAC, ServiceAccount/TokenRequest, managed Secret-backed TLS/registry resources, KAORI policy preflight, and admission enforcement evidence.

## Fail closed

Security-sensitive operations call the capability guard before provider mutation. A capability that is degraded, unavailable, or unknown does not silently downgrade the requested policy. Admission-dependent enforcement therefore must fail closed when ValidatingAdmissionPolicy/Binding capability evidence is unavailable.

Provider errors return an actionable code/capability/message but never kubeconfig, bearer token, Secret data, certificate private keys, or registry credentials.

## Reconciliation

The Native provider is an orchestration adapter over the existing canonical reconcilers; it does not clone them. Namespace intent uses existing Native Namespace/ResourceQuota/LimitRange reconciliation; access grants use existing Role/RoleBinding reconciliation; credentials use the existing ServiceAccount/TokenRequest lifecycle; managed resources use the existing platform-security reconciliation.

Provider operation results keep desired and effective hashes separate and expose non-secret committed evidence for drift, audit, and Intelligence.

Capsule is a separate provider implemented by #121/#124. Native baseline operation does not require Capsule and does not infer Capsule capability from CRD names or version alone.
