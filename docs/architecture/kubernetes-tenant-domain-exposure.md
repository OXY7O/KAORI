# Kubernetes Tenant Domain and Service Exposure Governance

Issue #119 defines hostname ownership and network exposure policy for Tenant Management. This policy is deliberately separate from RBAC: a principal may have Kubernetes permission to create a Service or Ingress while KAORI still denies the resource shape because it violates committed Tenant policy.

## Domain reservation

Administrators register hostname ownership against a Tenant Environment.

- **Exact** is the default. Reserving `x.com` authorizes only `x.com`; it never implies `api.x.com`.
- **Wildcard** is explicit and must use `*.example.com`. The apex is not implicitly included.
- **Regex** is explicit and validated. Because arbitrary regex overlap is not generally decidable, ambiguous regex ownership conflicts fail closed.
- Active reservations are collision-checked across Tenants on the same Kubernetes cluster.

Managed Ingress preflight accepts only hostnames covered by an active reservation for the namespace's Tenant Environment. Unknown/conflicting ownership is recorded as governance evidence.

## Service exposure

The default `ingress_only` profile allows ClusterIP and approved Ingress while denying NodePort, LoadBalancer, and ExternalName. Administrators may commit an explicit custom policy, but every exposure decision must be stated rather than inherited from permissive Kubernetes RBAC.

## Enforcement boundary

#119 owns canonical intent and preflight decisions. #120 owns Native Kubernetes capability evidence for admission/enforcement readiness. When a security-sensitive managed mutation requires admission enforcement and the connected cluster cannot provide it, the mutation fails closed.

Externally created resources remain provider-observed drift evidence for #123 Intelligence. This slice does not clone the Ingress controller or Kubernetes admission engine.
