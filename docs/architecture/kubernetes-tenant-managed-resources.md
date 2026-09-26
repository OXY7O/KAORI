# Kubernetes Tenant Managed Resources

Issue #118 defines the provider-neutral baseline for Tenant platform-managed TLS and private-registry resources.

## Authority boundary

Application teams may manage application-owned Secrets and ConfigMaps according to their Access Grant. Platform-security resources are separate KAORI-governed intents and carry explicit provider ownership evidence.

- **Platform TLS** is preferred. TLS termination remains outside the Tenant namespace so the private key is not exposed to Tenant administrators through normal namespace access.
- **Namespace TLS compatibility mode** is explicit and opt-in. KAORI materializes a `kubernetes.io/tls` Secret only from ephemeral material supplied by the guarded workflow.
- **Managed registry baseline** uses a `kubernetes.io/dockerconfigjson` image-pull Secret when a namespace Secret is required.
- **External credential provider** is the stronger registry direction when a connected Native/Capsule provider reports that capability Ready.

## Secret boundary

The canonical `TenantManagedResourceIntent` stores only non-secret intent and evidence: Tenant/Namespace identity, mode, resource name, source reference, lifecycle status, hashes, and rotation generation. Secret material is never persisted to the intent, Activity Log, reconciliation evidence, report payload, or routine UI.

Ephemeral secret material may exist only in memory while the provider mutation is executed. Provider evidence records a content digest and ownership metadata, never certificate private keys, registry auth values, or generated payloads.

## Ownership and drift

KAORI-managed namespace Secrets carry `app.kubernetes.io/managed-by=kaori`, Tenant identity, managed-resource identity, and `kaori.io/platform-security=true`. Reconciliation refuses to silently take over a foreign or application-owned Secret.

Rotation increments the managed-resource generation and replaces the effective Secret through the same ownership boundary. Removal deletes only the Secret owned by that intent. Missing or mismatched effective state is reported as drift/failure with non-secret evidence.

Advanced replication through Capsule remains owned by #124; provider capability readiness and fail-closed enforcement are finalized by #120/#121.
