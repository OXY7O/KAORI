# Kubernetes Tenant Audit Correlation

Issue #122 adds provider-neutral correlation between committed KAORI Tenant identities and Kubernetes API audit evidence.

## Evidence boundary

The external Kubernetes audit source remains authoritative for the raw Kubernetes audit log. KAORI does not copy request bodies, response bodies, Secret values, token material, managed fields, or arbitrary raw payloads into the operational database.

KAORI stores only bounded normalized evidence required for governance correlation: source/audit identity, source reference, Kubernetes principal/groups, Tenant scope where resolvable, credential/access ownership, resource/verb/outcome, timestamps, and explicit correlation status.

Ingestion is idempotent per cluster and source event. When `auditID` is unavailable, KAORI derives a stable digest only from the bounded safe normalized fields.

## Identity correlation

Managed ServiceAccount principals map through the canonical Tenant Credential `service_account_name` and Tenant namespace ownership. This includes human, administrator, and CI/CD credentials. A revoked or expired credential remains attributable so downstream Intelligence can detect evidence such as revoked-still-usable access.

Direct user/group principals may map through canonical active memberships and Access Grants when the namespace scope is unambiguous.

An unknown or unmanaged principal remains `unmanaged`. Multiple credible matches remain `ambiguous`. KAORI never guesses an owner to make the audit record look complete.

JumpServer command/session ingestion is not part of #122. Where a managed human credential already has a JumpServer reference, the normalized evidence carries that reference for later correlation.

## Activity and retention

Each newly accepted normalized record projects an audit-only Activity event through the existing Notification/Activity contract. It does not create a personal unread notification.

Normalized Tenant audit evidence registers with the existing Data Lifecycle archive/cleanup framework under `tenant_audit_evidence`, with a 90-day hot-retention fallback and 365-day archive-retention fallback unless an operator commits a different lifecycle policy.

Correlation failures and unmanaged/ambiguous identities are retained as explicit evidence for #123 Tenant Governance rules.
