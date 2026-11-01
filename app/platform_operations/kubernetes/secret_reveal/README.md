# Kubernetes Secret Reveal Administration

This Platform Operations domain owns governance configuration for Protected Kubernetes Secret Reveal. It does not read Secret values and does not execute reveal requests.

## Hierarchy

```text
Cluster
└── Namespace
    └── Disabled | Step-up authentication | Approval required
```

Cluster readiness has three independent prerequisites:

- primary cluster kubeconfig is configured;
- Kubernetes Secret encryption at rest is verified;
- Kubernetes Metadata-level audit logging is verified.

The kubeconfig prerequisite is read-only in Secret Reveal and is managed from cluster configuration. Namespace policy is explicit and default-deny. No policy row means Reveal is disabled. The Add/Edit Cluster form must not contain Reveal policy controls.

## Ownership

- `app/kubernetes/operations/secrets/reveal_policy.py`: canonical policy, readiness, and live namespace snapshot rules.
- `app/platform_operations/kubernetes/secret_reveal/service.py`: workspace context, summaries, filtering, and pagination.
- `app/platform_operations/kubernetes/presentation.py`: committed administration posture and implemented capability projections for the Overview.
- `app/platform_operations/kubernetes/secret_reveal/routes.py`: RBAC, CSRF, Activity Audit, operational toast, and save actions.
- `app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html`: protection posture and compact authorization boundary.
- `app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html`: cluster readiness and Kubernetes boundary.
- `app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html`: live-source evidence, filters, and namespace policy shell.
- `app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html`: namespace rows, policy mutations, and pagination.
- `secret_reveal_namespace_policies`: one unique policy per cluster and namespace.

Every save action emits shared operational feedback and a durable Operational Activity record containing only cluster, namespace, readiness, policy, and outcome. It must never contain kubeconfig or Secret data.

## Security rules

- Permission: `kubernetes_secrets.manage_reveal`.
- `clusters.manage` does not grant access to this page.
- A namespace cannot be enabled until all three cluster readiness prerequisites are satisfied.
- Enabling a namespace performs a fresh live namespace verification before the mutation is committed.
- A missing or unavailable live namespace source never silently grants access.
- Disabling cluster readiness immediately expires pending/approved requests and suspends all namespace policies without deleting them.
- Changing or disabling a namespace policy expires pending/approved requests for that namespace.
- The global environment switch remains outside the database and is displayed read-only.

## Live namespace source contract

The namespace policy workspace uses a process-local snapshot to separate **live-source refresh** from **search/filter/pagination**.

- The initial Secret Reveal tab load refreshes the selected cluster snapshot.
- Switching clusters refreshes that cluster snapshot.
- The explicit `Refresh` action refreshes the selected cluster snapshot.
- Search, policy filtering, page-size changes, pagination, and save-response rendering reuse the current snapshot and do not call the Kubernetes namespace-list API.
- If no snapshot exists, the first request may populate one so direct links still work after a process restart.
- Enabling a policy still calls `verify_live_namespace()` independently, so snapshot reuse never weakens the mutation guardrail.

Live namespace evidence has three states:

```text
Available  live refresh succeeded and the namespace exists
Missing    live refresh succeeded and the configured namespace does not exist
Unknown    live refresh failed; namespace presence cannot be asserted
```

When a refresh fails, the last successful namespace names may remain visible for continuity, but every row is marked `Unknown`. The UI must never convert a Kubernetes API failure into `Missing` evidence.

## Namespace list behavior

The list is server-side filtered and paginated.

- default page size: `5`;
- supported page sizes: `5`, `10`, `25`, and `50`;
- filters: namespace text, policy state, `Missing`, and `Unknown` live state;
- filter/pagination updates use HTMX with full-page fallback;
- policy saves preserve search, filter, page, and page-size context;
- rows remain compact and never repeat the selected cluster name.

The table contract is:

```text
Namespace | Live Namespace | Current Policy | Actions
```

`Live Namespace` uses `Available`, `Missing`, or `Unknown`. `Edit Policy` opens one scoped editor; `Save Policy` is explicitly disabled until its selection changes and never auto-submits. When cluster readiness is blocked or live presence is not `Available`, enabled policy options are disabled; an existing enabled policy can always be changed to `Disabled` so access can be revoked.

## Consolidated administration tab

- `/platform-operations/kubernetes/?tab=secret-reveal` is the canonical workspace.
- The tab loads lazily; opening Overview does not perform a namespace lookup.
- The initial Secret Reveal lazy load requests a live-source refresh.
- Cluster and explicit live-source refresh responses replace `#secret-reveal-cluster-workspace`.
- Search/filter/pagination update only `#secret-reveal-namespace-table-content`.
- No standalone Secret Reveal page hero or second page-local tab bar is allowed.

## No-reload mutation contract

Readiness and namespace-policy mutations use HTMX POST and replace only `#secret-reveal-cluster-workspace`. The full-page form action remains as fallback.

Each HTMX save response must:

- rebuild the canonical cluster workspace from server state;
- preserve cluster, namespace search, policy filter, page, and page-size arguments;
- update the browser URL through `HX-Push-Url`;
- trigger `kaori:notifications-changed` so shared operational feedback is rendered;
- update Secret Reveal Configuration counts/readiness and the parent Overview capability posture through HTMX out-of-band fragments;
- keep Secret Reveal active.

Operational toasts remain correct here because Save Readiness and Save Policy are immediate configuration mutations. Background execution progress must not be introduced into this workspace.

## Visual contract

- Secret Reveal Configuration uses compact, configured-state posture metrics; global enablement is read-only and runtime proof remains separate.
- A concise execution verification note preserves the policy, step-up, approval and Kubernetes RBAC boundaries without a decorative duplicate flow ribbon.
- Readiness Controls visibly include the read-only Cluster Credential prerequisite plus Encryption at Rest and Metadata Audit attestations.
- Activation Boundary uses a clear `bg-surface-card` surface.
- Kubernetes Boundary uses a clear KAORI card surface; it must not return to a solid Violet panel.
- Namespace Policies exposes live-source state, last successful refresh, and an explicit Refresh action.
- Table headers use Title Case and the reviewed responsive column contract `34% / 22% / 18% / 26%` with shared table primitives and horizontal overflow on narrow viewports.
- Shared semantic labels, pagination, dark-mode tokens, and KAORI Violet action hierarchy remain mandatory.


## Cross-workspace execution contract

Platform Operations owns configuration only. `Kubernetes Operations → Protected Kubernetes Secret Reveal` consumes the same `reveal_policy.py` readiness and namespace-policy authority rather than maintaining a second copy.

- target discovery requires current cluster readiness and configured enabled namespaces;
- protected target discovery verifies only configured enabled namespaces with Kubernetes Namespace `GET`, then reads the selected Secret live;
- request creation, approval, and one-time reveal re-check the current policy boundary;
- readiness disablement and namespace-policy changes expire matching pending/approved requests;
- administration snapshots optimize list rendering only and are never authorization evidence for plaintext reveal.

Dark mode for both workspaces follows the neutral-first KAORI contract: informational panels, table headers, hover states, and callouts use semantic/neutral surfaces; Bright Violet is reserved for primary actions and compact accents.


## v1.5 feedback and target discovery refinement

- HTMX readiness and namespace-policy mutations render their operational toast immediately with OOB delivery; redirect fallback alone uses the session feedback queue.
- The namespace-policy registry footer follows the canonical `Showing … Namespaces · Rows · page size` pattern.
- Protected Reveal does not depend on broad Namespace `LIST` for target discovery. It starts from policy-enabled namespace records and verifies only those names live.
- The Protected Reveal target selector explains global-disablement, cluster eligibility, missing policy configuration, and configured-but-not-live namespace states explicitly.

## Global Protected Reveal Gate

Namespace Policy enablement and the Protected Reveal deployment kill switch are intentionally separate controls. A Namespace can be configured as `step_up` or `approval_required` while Protected Reveal remains unavailable. Runtime target selection is enabled only after `KUBERNETES_SECRET_REVEAL_ENABLED=true` is loaded by the KAORI web application. Restart or redeploy KAORI after changing the environment value.

This is not exposed as an in-page toggle. Platform Operations owns readiness and Namespace Policy configuration; deployment configuration owns the global kill switch.


## Overview evidence taxonomy (KAD-01 / #1550)

Normal Kubernetes Admin GET uses committed canonical binding, credential-presence
metadata and manually verified encryption/audit attestations. They are
**configured prerequisites**, not current proof of successful Kubernetes API
requests. Enabled policy counts include configured namespace entries, while
`eligible_policy_count` requires the *same* registered cluster to have these
prerequisites and an enabled policy. Kubernetes Admin must not advertise
`Operational` solely from these counters; where eligible configuration exists,
show `Verification Required` until the live Namespace GET, Secret UID and
Kubernetes RBAC checks are completed by the actual Protected Reveal operation.
Normal Overview reads must never list namespaces or materialize fleet kubeconfig
plaintext. The global deployment kill switch remains authoritative.

High-risk readiness and namespace policy saves stage their source-linked
Activity Audit evidence inside the same database transaction; failure of the
evidence write rolls back the policy mutation. Routine toast/notification
transport may still use the standard best-effort path elsewhere.

## Scalable Kubernetes Administration Overview — review workstream #2605

The **Overview** presents committed KAORI configuration and a list of **implemented,
permission-owned administrative controls**; it is not a roadmap or a provider
feature catalog. `build_kubernetes_administration_summary()` returns
`administration_controls` and a computed `administration_control_count`, with
one current control: **Protected Secret Reveal**. Each control has a stable key,
workspace-tab target, status/tone, source-owned description, concise metrics,
read-only evidence disclaimer and a contextual configuration action.

Future administration capabilities must add their own authorized, source-owned
projection and workspace route under a separate approved issue. They must not
be displayed as live controls from speculative roadmap cards or assigned
Secret Reveal's authorization permission implicitly.

The overview intentionally distinguishes **registered clusters**, **configured
prerequisites**, **enabled namespace policies**, and **eligible configuration
scope**. The eligible scope is not live Namespace presence or current Kubernetes
RBAC evidence; the real Reveal path remains the authoritative live verifier.
Normal Overview GET continues to read committed database configuration without
loading kubeconfig plaintext or querying the provider.

`_administration_control_rows.html` is the single domain partial used in the
initial Overview and in `_summary_oob.html` after an HTMX save. Existing
`kubernetes-admin-*` Hero, status and metrics OOB targets are preserved; the
capability list/count are refreshed alongside them to avoid stale control
status without a page reload. A full-page fallback and the original
URL-backed workspace tab/HTMX namespace controls remain authoritative.

This is a **review/UAT candidate** under #2605, not a release lock promotion.
Human browser evidence across the six standard viewports, both themes,
keyboard and actual safe configuration state transitions is still required.
