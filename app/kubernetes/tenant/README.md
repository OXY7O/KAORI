# Kubernetes Tenant Management

Issue #61 is the parent product authority. Issue #125 owns the integrated Tenant workspace and final end-to-end UAT composition over the bounded implementation authorities #112–#124, #654, and #655.

## Product boundary

KAORI exposes one expandable `Kubernetes → Tenant` capability parent. Native Kubernetes and Capsule remain provider implementations behind the same canonical Tenant model and never become sibling product menus.

The approved Tenant destinations are:

- **Overview** — Tenant Collection Snapshot, multi-cluster estate posture, governed allocation/capacity evidence, prioritized operator attention, and recent Tenant activity. Navigation remains owned by the five Tenant sidebar destinations; Overview does not duplicate them as a Quick Actions strip.
- **Tenants** — canonical Tenant Registry plus a subordinate administration workspace for Tenant Setup, Memberships, Access Grants, Credentials, and Namespace Access.
- **Resource Profiles** — governed presets/custom profiles, allocation lineage, and capacity policy.
- **Namespace Provisioning** — namespace creation, allocation changes, ResourceQuota/LimitRange evidence, and capacity decisions.
- **Operations** — provisioning status, runs/evidence, drift/reconciliation, and Activity through internal Content Tabs.

### Cluster prerequisite and committed-read boundary

Tenant follows the shared #894 Provider Prerequisite Blocking contract while preserving #774 committed-read behavior.

- **No Kubernetes cluster registered** — Tenant is terminally blocked after the Hero. The canonical level-3 Tenant navigation remains visible for orientation, the normal Hero identity/metadata vocabulary remains stable, and the shared Kubernetes setup blocker owns remediation. Page-specific Tenant operational content is not rendered.
- **At least one cluster registered** — committed KAORI Tenant state remains readable even when live Kubernetes operations are restricted, validation is required, or the provider is temporarily unreachable. Live provider connectivity is presented separately and provider-backed mutations continue to fail closed.
- Zero-registration blocking must not be implemented from `native_available` alone. Registration existence and live/provider readiness are separate authorities.
- Provider absence must not hide route-level navigation; navigation expresses information architecture rather than evidence availability.

This preserves #750 terminal zero-cluster content blocking, #774 committed-state read availability, and #894 cross-domain navigation/Hero consistency without making normal Tenant pages depend on live provider requests.

### Tenant Detail: Namespace and Resource Profile correlation (#1136)

Use **Kubernetes → Tenant → Tenants → Tenant Registry → Tenant Detail →
Namespace & Resource Profile Mapping** to identify every displayed
Namespace's linked profile, public ID, pinned version, managed/observed
allocation control and frozen quota values, with its environment, generation,
Released/history status and last committed provider UID/reconciliation.
The preview deliberately shows **five newest records** and links to the
existing Tenant-filtered **Namespace Provisioning Registry** for full
history; this is a committed-only read model, not a new management form.
For a preexisting adopted Native Namespace without a linked profile, the
provider baseline is labeled **Observed/Imported** instead of claiming a
KAORI-managed profile. A linked Resource Profile's logical definition may
change without rewriting the pinned Namespace allocation version.

For a Native lifecycle test, record provider `ResourceQuota`/`LimitRange`
specifications and metadata at these checkpoints: **before Adoption**,
**after managed Allocation Change + verified read-back**, **after Native
Release + verified handoff**, **after independent Handback**, and
**after explicit fresh Discovery/Re-adopt**. Adoption initially records
the observed provider allocation and the governed takeover may preserve
equivalent values; only explicit admitted allocation mutations change
Kubernetes allocation specs. **Release does not resize Kubernetes
resources**: it transfers ownership/governance labels and verifies that
effective quota/limits and foreign metadata remain unchanged. Subsequent
Handback and verified residual-label recovery are metadata-only; new
Adoption creates a new committed generation. Do not interpret the mapping's
CPU/memory values as live utilization or assume `Released` proves that
Re-adopt is already eligible. Provider execution/official UAT remains
HOLD unless separately authorized.

### Resource Profile lifecycle

Resource Profile administration preserves the approved #113 allocation authority while avoiding profile sprawl:

- **Small / Medium / Large / Extra Large** keep server-authoritative numeric sizing values fixed. Operators can revise the **Managed ownership mask** and **Advanced Controls**; a contract change increments the same logical profile to the next version.
- Built-in revision never accepts operator-supplied numeric values. Canonical preset values are rehydrated server-side, so `Small vN` cannot silently redefine Small sizing.
- **Custom** profiles remain fully operator-managed. Edit may change name, description, enabled state, quota, storage guardrails, Container LimitRange values, and Advanced Controls.
- Existing Namespace allocations remain pinned to their committed `resource_profile_version` and frozen allocation snapshot after any profile edit.
- Resource Profile Registry exposes pending rollout state. **Attached Namespace Rollout** applies the current version to active Native Namespace attachments for one selected Tenant; each Namespace independently passes capacity admission, provider mutation, and read-back.
- A failed Namespace rollout stays on its previous committed version. Capsule attachments continue through Capsule-specific admitted governance paths; the Native rollout action never bypasses Capsule authority.
- **Hard Delete** remains limited to Custom profiles with **zero Namespace references and zero Capacity Decision references**. Built-in logical profiles cannot be deleted.
- Disable stops future selection without deleting historical profile identity or evidence.

Namespace Provisioning and Operations follow the same KAORI page hierarchy established by Tenant and Resource Profiles: **Snapshot → Estate → Workspace → focused Content Tabs**. Namespace Provisioning separates Provision Namespace, Allocation Change, and Capacity Decisions while the Namespace Registry uses canonical filters and default-five pagination. Operations separates Provisioning, Runs & Evidence, Drift & Reconcile, and Activity without creating third-level sidebar destinations.

Operations task views stay inside the page so the sidebar remains exactly two interactive levels. Only the five approved Tenant destinations are supported; superseded workspace routes are not retained.

## Evidence and provider authority

Normal Tenant workspace reads are composed from committed KAORI state. Live provider calls remain inside the owning mutation/reconciliation adapters, plus explicitly live surfaces such as Provider Connectivity and Tenant Discovery.

### Committed read model and Native provider readiness

Native Kubernetes remains the mandatory baseline provider for Native Tenant mutations. Tenant does **not** depend on Analytics, Metrics Source, or Alertmanager. Provider-backed mutation readiness follows the canonical Kubernetes runtime contract: the cluster must be connected, explicit `ready` or `degraded` validation states are operational, and a connected legacy registration with a null readiness field uses the connected-implies-ready compatibility fallback. `validation_required`, `blocked`, unavailable, failed, or disconnected states remain fail-closed for provider-backed mutations.

Provider readiness is **not** a page-level read gate. Tenant Registry, Resource Profiles, committed Namespace state, access/credential metadata, Operations evidence, and committed capacity/snapshot evidence remain readable from KAORI state even when the Kubernetes API is unavailable. With zero cluster registrations the setup guidance remains visible, but committed KAORI records are not hidden. With a registered but non-Ready provider, the Hero reports **Provider Operations Restricted** while the committed workspace remains available.

The two snapshot concepts are intentionally separate:

- **Tenant Collection Snapshot** — committed evidence produced by `kubernetes.tenant.sync`; it retains last-success, source cutoff, scope, coverage, and exceptions while the provider is offline.
- **Live Provider Connectivity** — a short, explicit live Kubernetes API reachability probe. The on-demand endpoint remains available for supported operational flows; routine Tenant page reads do not perform live probes, and child pages do not expose a second connectivity panel. A probe result never replaces the committed snapshot.

This boundary does not weaken mutation safety. Create/provision/reconcile/credential/provider mutations continue to use their owning readiness/capability checks and fail closed. Discovery from #736 remains the explicit live-provider read exception.


Routine Tenant reads also keep expensive supporting evidence bounded. Operations uses the canonical Namespace/Tenant registries with workflow/decommission support disabled when those controls are not rendered. Tenant Overview batches KAORI-owned capacity policy, committed Namespace allocation, Capsule shared-allocation evidence, and committed Capacity Analytics snapshots across the registered cluster estate before applying the existing per-cluster capacity classification and operational sort. Snapshot freshness and stale/blocked semantics continue to use the canonical materialization reader; no live provider request or new cache is introduced.

Tenant Overview owns a registered **Tenant inventory correlation** job while Kubernetes remains authoritative for observed cluster resources:

```text
Kubernetes provider observation
→ kubernetes.inventory.sync
→ committed Kubernetes inventory

KAORI Tenant state + committed Kubernetes inventory
→ kubernetes.tenant.sync
→ worker-generated Tenant Collection Snapshot
→ Tenant Overview
```

`kubernetes.tenant.sync` runs through the canonical Platform Operations registered-job scheduler and the existing `inventory` worker queue. It does not introduce a Tenant-specific scheduler framework and it does not perform Tenant reconciliation or provider mutation.

Non-Overview Tenant pages (Tenants, Resource Profiles, Namespace Provisioning, and Operations) render **one canonical Inventory-style Snapshot Context Bar** beneath the Hero, reusing `components/snapshot_context_bar.html` through the existing `_collection_snapshot_context.html` partial. The bar preserves status, source, last successful collection, committed scope, committed namespace coverage, and snapshot exceptions — including `Not Collected`/stale/partial states. The same committed snapshot bar also remains on **Overview**, where **Sync Tenant / Configure Sync** actions are unchanged. Child pages render no Live Provider Connectivity panel or Check Live Connectivity action and issue no provider probe during normal committed reads.

Overview actions follow the established operational sync pattern:

- **Sync Tenant** — manually dispatch `kubernetes.tenant.sync`.
- **Configure Sync** — open the registered-job policy for automatic cadence.

The existing global **Sync All Inventory** quick action remains the cross-domain orchestration entry point and includes Tenant sync alongside Kubernetes/Object Storage inventory domains allowed by the operator's permissions. Tenant Overview does not duplicate that global action.

Successful manual dispatch follows the TLS synchronization behavior: the HTMX click updates worker progress without creating a completion toast or incrementing the Notification Deck immediately. The worker persists the operator notification only when the job reaches a terminal state, with Tenant/namespace/cluster coverage and exception evidence from that completed snapshot.

Capacity Analytics remains a separate committed evidence authority. Tenant sync must not fabricate missing capacity data or imply that refreshing Tenant inventory refreshes `analytics.capacity`. Overview keeps per-cluster capacity information compact: posture, freshness, and a path to Capacity Analytics are shown instead of detailed allocation tiles or meaningless `N/A` values. The cluster estate follows the canonical KAORI table and pagination contract with 5 rows by default and 5/10/25/50 page-size choices; full fleet inventory remains owned by Kubernetes Inventory.

- Native Kubernetes is the mandatory baseline provider.
- Capsule is capability-aware and optional.
- Degraded/unavailable Capsule capabilities fail closed.
- Provider state and reconciliation authority are explicit committed evidence.
- Capsule-only advanced mutations require admitted compatible capability evidence.
- Native Recovery remains an explicit governed authority transfer, never an automatic fallback.

### Capsule Namespace onboarding: Adopt vs Attach (#1124)

Use **Tenant → Tenants → Discovery** as the only primary entry point for
onboarding. **Review Adoption** imports a new Capsule Tenant and all
Namespaces already proven to belong to it; no separate Namespace-attach
step is needed. If the Capsule provider later creates an additional
Namespace under that Tenant, Discovery presents the *ungoverned,
correlated* Capsule Namespace candidate as **Review Attachment** and
uses the same existing read-only preflight, UID/resourceVersion checks,
Environment selection, and canonical `/discovery/adopt` service.
Already governed or blocked Namespaces cannot be attached again.

Tenant Management no longer presents the unconditional **Available →
Attach Capsule Namespace** accordion; that controls onboarding rather
than Release/governance. Attachment does not modify Capsule CR, Namespace
quota, RBAC or provider-owned values. It adds a verified KAORI mirror
record only, never new implicit access grants. Source-only UI changes
and regression test contracts are authored; runtime/gate verification HOLD.

## Tenants workspace composition

The Tenants destination keeps a small page-level governance summary visible above one tabbed workspace:

```text
Hero
→ Multi-Cluster Posture
   └── Tenant Estate
→ Tenant Workspace
   ├── Tenant Registry
   ├── Tenant Setup
   ├── Memberships
   ├── Access Grants
   ├── Credentials
   └── Namespace Access
```

`Tenant Registry` is the default tab and uses the canonical KAORI server-backed registry contract: shared loading bar, Cluster/Environment/Lifecycle/Search filters, committed-state reads, semantic labels, responsive horizontal overflow, default 5-row pagination, 5/10/25/50 page sizes, and HTMX progressive enhancement with the Tenants route as the real navigation fallback.

**Native external provider handoff read-back preconditions (#1095 follow-up):**
The read-only external inspection action requires *current* committed
independent plan/approval, matching SHA/fingerprint, same-plan external
reference and fresh exact-scope Native dry-run. Showing historical
`Dry-Run Passed` or a reference claim alone does **not** mean it can be
submitted. The server continues to enforce complete evidence freshness,
tenant identity, UID/resourceVersion and provider authorization before
any Kubernetes read.

Step 3 now shows `External handoff inspection is unavailable` with
the specific missing evidence instead of a doomed confirmation checkbox.
When the approval expired, use the original-requester restart control in
Step 4 and re-establish reviewer, reference and dry-run for the **new**
SHA. If all prerequisites are current, the separate
`Inspect External Handoff` form is available only after an *external*
operator truly transferred provider ownership markers. This read-only
observation is **not** the KAORI-governed handoff executor, does not
verify successor consent, and cannot authorize Release. A read-back
count from an earlier attempt is labeled as historical evidence.

No provider mutation or new authorization, no source-of-truth change,
no new form, CSRF or gateway bypass. Contract/unit tests written but
not executed; browser Visual QA and admission/CI/CD HOLD.

**Tenant Release wizard navigation and feedback (#1095; current UX):**
Step 1–4 tabs, Previous/Next and internal step links now fetch a committed
Tenant Detail fragment through HTMX and **swap only the Release Governance
card**, preserving the Tenant Overview, canonical URL/history, and original
plain `href` fallback. The server returns
fresh committed state for each step and never calls Kubernetes solely to
render navigation. History snapshots are disabled for the sensitive
Tenant Detail to avoid stale approval evidence on Back/Forward.

Every existing Tenant governance POST still includes the original CSRF,
resource identity, plan SHA and HTMX response/toast. Submit buttons are
temporarily disabled by HTMX while an action is in flight; the loading
indicator shows pending work. Server-recorded operational feedback is
rendered near the active Release step as well as in the global Operational
Toast. The inline result is **not** a replacement for checking committed
preflight/approval/handoff/read-back evidence. Required checkboxes are
intentionally reset after a POST or page navigation: they represent
one-time consent to send that specific request, **not** persisted evidence
that the action was accepted. Operators should inspect the request result
and Activity Audit, then the current stage status, before attempting
another governed action.

No new client storage, bypass, provider API, form endpoints, automatic
approval, new UI taxonomy or changes to any of the 14 Tenant forms.
Local browser Visual QA and CI/CD/admission gates remain HOLD.

**Native Platform Admin verified TLS prerequisite (#1047 follow-up; current UI):**
A successful independent approval is not sufficient if the registered
Kubernetes connection has `verify_ssl=False` or no trustworthy connection.
Step 3 now shows **Verified TLS Required** with a permission-scoped edit link
and does not render the Native Platform Admin acceptance POST when TLS
certificate verification is disabled/missing. Step 4's **Next required action**
shows the same configuration prerequisite if review and approval are current.
Provider verification still requires server-side verified transport,
SelfSubjectReview with a trusted principal, scoped SelfSubjectAccessReviews
and explicit operator consent. This is a read-only hint/gate in the UI,
never a substitute for backend checks.

For operator remediation, edit the cluster's canonical **Kubernetes
Connection Configuration**, confirm kubeconfig CA and API server certificate
name, check **Verify Kubernetes API TLS Certificate**, **Test Connection**,
save, and complete **Full Validation** before retrying the Release flow.
Do not toggle DB state directly or weaken TLS. Connection updates are
operational mutations requiring separate approval. existing governance forms and
original provider safeguards preserved. CI/CD, security checks, UAT HOLD.

**Governed no-transfer recovery after a failed executor (#1104, child of #1057):**
A historical Native executor attempt still blocks ordinary expired-plan
restart. A reported `0/2 verified` and `provider_mutation_performed=False`
do not authorize a retry, even when Kubernetes labels currently show
`managed-by=kaori`.

The bounded Step 4 workflow is:
- Original requester: **Assess No-Transfer Provider State**. The server
  checks every complete same-SHA, same-executor started/failed-before-write
  pair in chronological order and rejects orphan, duplicate, changed actor,
  partial/unknown/mutating receipts or non-canonical same-plan read-back.
  All historical executor/read-back records are SHA256 digest-bound.
  The assessment also rechecks original dry-run identities and hashes,
  fresh provider inventory, metadata/spec/foreign-label preservation and
  dependency counts. Only read-only Kubernetes GETs occur; a SHA-bound
  assessment is committed to AuditEvent.
- Independent recovery reviewer: **Authorize Reviewed No-Transfer Recovery**
  only when different from the original requester/assessor. For this
  canonical verified-no-transfer path, the failed executor may be the
  second operator; no third operator is mandatory. This does not relax
  the full historical provider/read-back verification. The decision binds
  the exact assessment, expires and never authorizes Kubernetes PATCH
  or Release.
- Original requester: **Restart with Fresh Provider Verification**.
  All provider/history evidence is verified again and an immutable new
  pending-independent-review Plan SHA replaces the expired plan. No previous
  approval, reference, preview, Platform Admin identity consent or released
  state is inherited. Existing independent approval + Native trusted
  acceptance/dry-run workflow still applies.

The panel is committed-read-model UI only and not permission authority.
Endpoints separately enforce Tenant/Integrations/Cluster manage RBAC,
CSRF, actor separation, exact SHA and the existing fail-closed gates.
Unknown/partial/full transfer and any provider/history drift still
require a separate manual investigation. **Do not erase AuditEvents,
manipulate timestamps/labels, retry blindly, or treat successful source
checks as completed recovery.** Tests/UAT/CI/CD remain HOLD.

**Native expired-plan recovery with 0 transferred resources (#1057 follow-up):**
A `provider_handoff_not_started` receipt may permit the original requester
to **attempt** Restart Expired Handoff Plan only when its complete canonical
evidence proves all exact originally approved provider objects are still
pending, UID/resourceVersion and preservation hashes match, no prior
partial/full marker transfer or executor event exists in committed history,
and every release/mutation flag is false. A bare `observed_count=0`,
missing/legacy receipt, or unknown/partial/full observation does not
permit restart. Before superseding the old plan, KAORI performs a fresh
authoritative Kubernetes Release preflight and checks the same plan,
fingerprint, UID/RV, zero dependencies and all committed audit history
again under the existing Tenant lock. The replacement SHA keeps immutable
lineage and must be independently approved by another operator. No prior
reference, dry-run or acceptance is inherited; no provider write occurs.

The Step 4 **Next required action** differentiates eligible zero-transfer
evidence from transfer/recovery-required evidence. A reviewer cannot
restart a requester's plan. Step 3 no longer offers Native Dry-Run on
expired review/approval; use Step 4 requester renewal instead. The
display projection is **not** an admission gate; backend checks remain
authoritative and fail closed on any drift. This is recovery **only** when
provider handoff has not begun, never for partial/full handoff.

Contract/unit tests and browser QA are pending, as are CI/CD gates, Full
Admission, staging/UAT and deployment; no production migration performed.

**Read-only executor no-transfer assessment (#1110):**
Step 4 identifies one or more complete same-plan executor started/failed
pairs. The initial audit is written before terminal mutation counters exist;
every failure must explicitly report zero verification and no mutation.
Orphan, inconsistent, mutating or incomplete history stays blocked.
`no_transfer_assessment_candidate` is an **advisory committed UI signal**,
not an approval, successful provider read-back, restart permission or
automatic retry. Existing backend fail-closed guard continues to block
same-plan executor attempts. Operator must verify original provider scope,
UID/resourceVersion, full spec and retained metadata, dependencies and
immutable audit evidence via the existing #1104 governed workflow before
any new SHA/approval or Kubernetes mutation. The candidate hint is never
a substitute for requester assessment or an independent recovery decision.
No live provider checks were run for #1110; QA and gates HOLD.
The assessment backend rejects incomplete/odd executor receipts, unsafe
pairs and any same-plan read-back not proving canonical no-transfer. The
read-only historical predicate does not replace the fresh TLS-verified
provider GET, independent decision or new-plan review. Operators must
inspect Activity Audit and never infer safe restart from a 0/2 counter.

**Bounded multi-attempt Native recovery (#1118):**
DevContainer evidence contains two committed started/failed executor pairs
under the same original Plan SHA, with zero verified components, explicit
non-mutation terminal flags and four canonical read-back receipts. #1118
allows *one or more* complete chronologically ordered failed-before-write
pairs **only** for the same executor actor, original plan/fingerprint and
approved scope. Every failed receipt requires zero verification and an
explicit non-mutation result; every read-back must satisfy the original
canonical predicate. All history stays SHA256 digest-bound, and new
assessments record all failed event IDs and the total attempt count.
Existing fresh authoritative Kubernetes GET, verified TLS, original dry-run
UID/RV/spec/foreign metadata and dependencies, original requester,
independent second-operator review (which may be the original executor,
but never the requester) and new-plan approval remain mandatory.
Candidate status never grants restart, provider mutation or Release.
Tests/CI/CD/UAT/deployment remain HOLD; this is source-only integration.

**Native executor approved-component patch binding (#1102 corrective under #1048):**
`dry_run_native_handoff_component` commits authoritative Kubernetes
**preview evidence**, not a governance ownership decision. Executor patches
must bind each receipt's exact namespace/kind/name/UID and original
resourceVersion back to one uniquely approved handoff component from the
current SHA-verified plan. The approved component must explicitly carry
`external_acceptance_required` and `kaori_marker_correlated`; the full
scope is checked before recording an in-progress attempt or sending any
provider mutation. Only this approved component is passed to the current
metadata-only conditional successor JSON PATCH builder. Dry-run receipt
hashes remain the source of pre/post spec, foreign metadata and immutable
identity verification; provider and backend authority never moves to the
presentation layer. Reject mismatched/ambiguous/missing authority.

This corrects the first ResourceQuota `ValueError` produced when the
executor sent a preview receipt lacking the two plan-only fields to the
patch builder. The existing historical failure remains an AuditEvent and
requires separate, explicit provider-authoritative recovery review; do not
reset audit history, inherit expired approval or blindly Resume. No
live mutations or provider tests were made as part of the fix. Source
regressions authored; all CI/CD, admission and staging UAT gates HOLD.

**Native executor recovery priority in Release Steps 3/4 (#1091 follow-up):**
When the most recent current-plan Native handoff executor AuditEvent is
`partial_handoff_recovery_required`, the shared committed readiness
projection and both Release step headers prioritize **Recovery Required**
over generic Transfer Pending or Verification Required. The fourth
checkpoint remains incomplete; 3/5 indicates internal approval evidence
only. Read-only Step 4 details show exact attempt verified/expected
resource count, whether mutation was reported, and sanitized failure
summaries; 0 verified must never be interpreted as 0 resources changed.
Find `tenant.release.native_handoff_recovery_required` in Activity Audit,
correlate `plan_sha256`, inspect the authoritative Kubernetes state and
only then decide whether an existing permitted recovery operation is
appropriate. Actor-specific forms stay unchanged: the accepted Platform
Admin alone can see the eligible Resume action; the other account can
still see permitted read-only dry-run. No automatic retry or new Release
admission is created. Validation/UAT and CI/CD gates remain HOLD.

**Native Release Step 3 expiry + Step 4 recovery UX (#1091; current):**
The Step 3 **Transfer Pending** label is no longer shown for stale
independently acknowledged Native plans. Display **Approval Expired** or
**Review Expired** from committed `native_release_readiness`, link to
Step 4 and keep Platform Admin acceptance invisible when either plan/
approval or provider review freshness is invalid. The existing backend
15-minute identity/approval/fingerprint and separation-of-duties checks
are unchanged and still authoritative at submit time.

Step 4 now shows five read-only checkpoints and a compact **Next required
action** area rather than one long text panel. Eligible original requester
can explicitly restart an expired acknowledged plan with the original
CSRF/HTMX POST and exact SHA; other users are instructed to contact the
requester, while prior provider read-back requires manual recovery.
Read-only source-of-truth language, pending and review-expired navigation,
Release/Finalize gates, all 14 original forms, provider identity,
external-reference status and audit lineage are preserved. No live
provider fetch in normal UI; no automatic mutation. DevContainer Visual
QA pending and every CI/CD/admission gate remains HOLD.

**Tenant Release Step 3 — independent approval evidence (#1089; current UI):**
In the four-step Native/Capsule Release wizard, the independent-approval
step now separates a compact locked-plan state and original Successor owner /
Change record from an untruncated monospace Plan SHA-256, the
independent-review acknowledgement, and the **External Reference Unverified**
claim. A standalone focused Platform Admin verification form retains
existing X.509 registered Kubernetes connection, permission proof and
required explicit consent checkbox before submission. Treat independent
review, external successor evidence, verified successor consent, provider
handoff and read-back as **different states**; none are inferred from a
plain-text reference. Preserve native/Capsule gating, original requester
restart, audit, all Step 3 POST endpoints, 14 CSRF/HTMX forms, global toast,
and provider-authoritative checks. The change is visual hierarchy and copy
only. Tests/DevContainer human QA are pending; CI/CD admission stays HOLD.

**Managed allocation blocker/admission copy compatibility (#1085 corrective):**
The longer Resource Profile-linked allocation message from
`release_preflight._release_blockers` must be recognized as the *known
external handoff obligation* by
`release_handoff_approval._EXPECTED_HANDOFF_FRAGMENTS`. Previously,
the preflight copy changed while the admission allowlist still matched
the obsolete text, creating a false-positive `Unresolved provider,
identity or governance blockers prevent approval` on expired-plan
restart. The narrow mapping is restored with a regression test that
passes actual preflight output into `_can_confirm_plan` and rejects
unrelated provider identity blockers. All existing independence,
freshness, provenance, dependency, UID/RV and partial-readback guards
remain intact. This is not a handoff or Release authorization; run
DevContainer human review before any gate/promotion. CI/CD HOLD.

**Tenant Release Step 2 — compact resource summaries (#1085; latest UI):**

DevContainer refinement removes repeated vertical gaps in Provider
handoff scope. A single short heading now includes the committed total
resource count, while the original handoff-required status badge remains.
Each resource's **native `details` summary** is one clickable two-line
row: icon, full Kind/Name, original semantic status, and inline labeled
Namespace (when distinct), Ownership and Manager. The on-row **Provider IDs**
cue opens exact committed Namespace/UID/resourceVersion, with full-width,
wrap-safe detail values. This replaces the old separate Ownership/Manager
grid and separate identifier toggle line (no nested scrollbar, new tab,
component framework, or provider API). Keep initial evidence read-only,
its original empty states, provider authority, protected Release flow and
all 14 CSRF/HTMX forms intact. Tests and local browser review pending;
all admission/CI/CD gates remain HOLD.

**Tenant Release Step 2 — provider handoff resource evidence (#1085; historical first pass):**
Render the four-stage Release wizard's second step as one clear structured
resource list rather than dense provider text rows. A compact summary uses
committed `handoff_required_count` and `handoff_components|length`; each
resource shows its exact Kind/Name, Handoff Required/Ownership Conflict/
Observed semantic label, and distinct Ownership evidence and Provider manager
facts. Exact provider Namespace, UID and resourceVersion are kept under
native keyboard-accessible `Provider identifiers` disclosures. Show the
original not-collected and no-handoff messages distinctly, with no false
ready/approved state. This is committed Release preflight evidence only;
Kubernetes/Capsule remains authoritative, and provider handoff/Release never
occurs from merely viewing this list.

The `release_preflight._release_blockers` copy for an adopted Namespace with
a linked Resource Profile now explicitly states the need for approved
provider allocation handoff and verified read-back; its admission guard
is unchanged. All 14 original CSRF/HTMX governance forms and step URLs,
independent approval, native provider verification, styling and global OOB
toast remain unchanged. All CI/CD gates and local human Visual QA remain HOLD.

**Tenant Overview — integrated authority and lifecycle (#1081 follow-up; current UX):**
On the same compact Overview surface, retain exact Provider and
Reconciliation Authority facts but remove their redundant full-size
**Provider Authority** accordion. The Reconciliation field owns the prior
`#tenant-provider-authority` deep-link anchor. Move the precise
Kubernetes/Capsule source-of-truth statement out of the large
**Authority Boundary** callout into a small neutral Overview note. Place
the existing Decommission/Retry and blocker preflight in one collapsed
**Lifecycle controls** row at the bottom of Overview, retaining
`#tenant-lifecycle-actions`, the lifecycle section auto-open state,
permission guards, exact POST/CSRF/HTMX fields and native destructive
confirmation modal. Release/Handback/Attachment and global toast behavior
remain unchanged; there are still 14 original form authorities.
Hero subtitle: “Manage Tenant governance, provider authority, and lifecycle
with committed evidence.” No new provider read, grant or mutation contract.
DevContainer visual QA and all CI/CD gates remain HOLD.

**Tenant Overview — compact committed record (#1081; historical foundation, superseded standalone boundary placement):**
DevContainer feedback supersedes the former #1081 two-subpanel + Record
History band layout. Reuse one existing bordered Violet KAORI surface with
a **small Identity & Governance header**; show exact wrapped/monospace Tenant
ID on one line/row, then a responsive 4/2/1-column plain facts grid:
Cluster, Provider, Ownership, Lifecycle, Reconciliation Authority, Generation,
Registered, Last Updated. Keep canonical semantic lifecycle status and
`Not recorded` date fallbacks, with the small historical Namespace footnote
only if applicable. Put the full Description in a single inline-label bottom
row, safe for long text/newlines and without whitespace indentation artifacts.
Do not repeat #1079's KPI cards, reintroduce Quick Links, or introduce a new
UI system/provider request. Preserve all 14 forms, Release wizard and the
standalone Authority Boundary note. DevContainer Visual QA / CI/CD HOLD.

**Tenant Governance Scope — canonical shared posture card (#1079; current UI):**
Match the existing Tenant Overview `Governance Scope → Tenant Estate`
layout using `section_intro`, `operational_section_card.render` and
`resource_posture_grid.render(columns=4)`. The single header panel
is titled **Tenant Governance**; its four shared posture cells read
**Active Namespaces, Environments, Reconciliation Authority and Lifecycle**
from committed Tenant evidence. This replaces the two independent
Resource Coverage/Governance Authority cards from #1077, not the
provider-authoritative boundary note or any governance action.
Do not mix fleet-wide Tenant/Credential/Finding counts into one-Tenant
detail. The shared component owns responsive separators, metrics/icon
layout and light/dark styles. Runtime browser Visual QA and quality gates
remain pending.

**Governance Scope and Release Review refresh (#1077; historical workflow authority; scope presentation superseded by #1079):**
The four separate Tenant KPI tiles are replaced by a grouped
**Governance Scope** (Resource Coverage and Governance Authority) composed
only of committed Namespace/Environment, reconciliation and lifecycle
data. A separate neutral **Authority Boundary** info box explains that
KAORI presents committed evidence while Kubernetes/Capsule remains
provider-authoritative; the historical Namespace count remains available.

Release Governance is **always visible**, with an icon header rather than
numbered outer disclosure. The four existing Release wizard steps remain
URL-addressable; the Review Scope step presents a short readiness
summary, original Review Release action and an optional exact
**View recorded conditions** list. This reduces initial text density
without deleting blocker evidence. Two redundant instructional footnotes
were removed from the interface without changing any authority gate.
Other governance sections remain conditional expandables. Same 14
CSRF/HTMX actions, reviewed handoff, committed audit and toast; no new
provider mutations. Browser Visual QA and execution/security gates
remain pending.

**Tenant Overview and Release wizard (#1075; historical revision):**
Keep the existing KAORI two-column Violet Hero/context card, but shorten its
subtitle to "Manage Tenant governance and lifecycle." Historically, replace the old
identity table + Description/Quick Links with distinct **Identity & Origin**
and **Governance State** surfaces (now superseded by #1081). No Quick Links; source all factual values
from committed Tenant and Cluster records, with guarded timestamp and
historical Namespace display.

For ready governed Tenants, Release Governance offers a real four-stage
`release_step` URL workflow rather than immediately displaying every form:
1. Review Scope (preflight/blockers), 2. Provider Scope (inventory),
3. Approval & Handoff (independent plan, consent, guarded execution),
4. Verify & Finalize (evidence read-back and Released commit). Only the
selected step renders. Links are navigation only, not admission: original
service-side plan freshness, separate reviewer, CAS and provider read-back
remain authoritative. Next/Previous and full reload preserve the Registry
context; HTMX POST keeps the active stage through `tenant_release_step`
and displays the normal global OOB toast. Work Inbox opens the Approval
stage directly. Unsupported stage values fall back safely to Scope.
No extra provider requests on ordinary GET or new mutation endpoints.
All gates and real cluster/Visual UAT remain HOLD.

**Tenant Details approved visual composition (#1073; Hero/accordion foundation; Overview/Release layout superseded by #1075):**
Use existing full-size Violet two-column Hero with shared `page_hero.context_card`
for a contextual Tenant Details right-side panel, two committed metrics,
lifecycle status and the full-width Back to Registry. Under it show four
responsive summary cards and a two-column Tenant Overview with identity,
description, audit-lineage note and links to existing KAORI registry/services.
Use five native keyboard-accessible expandable governance sections instead
of a long wall of forms or secondary Content Tabs. Release opens with a
four-stage preview but keeps the detailed independent approval, provider
handoff and finalizer controls folded until requested. Independent Work
Inbox links expand Release immediately. All 14 existing forms carry
`tenant_detail_section`, their prior CSRF, exact resource identity and
Registry state. After POST the active permitted section reopens and the
global OOB toast remains visible; Decommission alone retains its short
destructive confirmation modal. Normal detail GET is committed-only.
Earlier stacked/modal/tabbed layouts were rejected during Human Visual QA.
Runtime Visual QA/security gates remain pending; no staging release implied.

**Tenant Management single-page correction (#1071, superseded historical design):**
The user rejected both the oversized dashboard (#1067) and the secondary
Content Tabs workflow (#1069). The current detail is one naturally scrolling
page with the exact shared KAORI Violet Hero sizing, layout, intro/title,
description and metadata classes. It has a single Back to filtered Registry
action, the normal Tenants active navigation and canonical global breadcrumb.
A concise Tenant Overview is followed by clearly described, full-width
governance sections: Release (four divided phases with readable blocker and
inventory evidence), Platform Admin Handback, Capsule Attachment, Provider
Authority, and Lifecycle. Sections appear only where applicable and
authorized. No custom Hero overrides, nested modal framing, second tab row,
sticky sidebar, oversized KPI cards or internal inventory scrolling.

All 14 existing governance POST forms, CSRF, provider authority, independent
review, exact Tenant identity, and Registry filters remain unchanged. The
entire detail including Hero is refreshed by HTMX and emits the existing OOB
Operational Toast; the non-JS POST returns to the same page. The Work Inbox
link scrolls directly to the Release Governance section. Only short
Decommission confirmation remains modal. No provider or permission rules
were changed. Browser Visual QA and gate admission remain pending.

**Dedicated Tenant Management (#1065):** a Registry row's single
`Manage/View` action navigates to `/kubernetes/tenant/tenants/<tenant-id>/manage`,
a full-width, responsive, committed-state Tenant detail page. It retains
Registry search/filters/pagination on the **Back to Registry** link and
provides in-page navigation for provider ownership, Release governance,
Capsule attachment, Native handback/Re-adopt and lifecycle actions. It does
not expand below the table or open the removed long native Tenant Management
dialog. Independent approvers from Work Inbox deep-link to the same detail
page instead of reopening a top-layer dialog. Every form keeps its existing
authoritative backend endpoint, CSRF token, permission gate and audit
metadata; both progressive HTMX swaps and ordinary POST redirects return
to the same Tenant detail rather than a Registry modal. Normal HTMX
feedback continues using the existing OOB Operational Toast, which stays
visible because the daily management page is not in the browser's modal
top layer. Decommission retains its separate concise destructive confirmation
modal. Normal detail GET performs no Kubernetes provider request.

`Tenant Setup` combines the create form with a non-collapsible governance flow so the operator sees the required order: Tenant → Namespace → Membership → Access Grant → Credential. Important boundaries use icon-backed tiles plus a persistent warning row. Dense field guidance uses the shared `components/info_tip.html` hover/focus pattern instead of repeating helper paragraphs under controls.

Tenant Setup supports two direct-create provider paths while retaining one provider-neutral UI. **Native Kubernetes** creates the KAORI Tenant boundary without a first-class Kubernetes Tenant object; Namespace resources are introduced later by Namespace Provisioning. **Capsule** performs its live supported-CRD/capability and admission preflight when **Add Tenant** is submitted, requires both an initial Owner Kind and Owner Subject, dry-runs the exact Tenant CR, then creates the authoritative Capsule Tenant CR before committing KAORI provider evidence. Existing Capsule Tenant CRs are never overwritten and continue through **Discovery → Adoption**.

`Memberships` separates three peer actions (add user, create group, add group membership) from scalable registries. Successful administration mutations progressively refresh only the Tenant Workspace through HTMX rather than forcing a full-page navigation/scroll reset. Membership and Tenant Group data each use canonical filtered/paginated tables instead of fixed recent-item lists.

`Access Grants` keeps one full-width multi-column form above the canonical Access Grant Registry. The registry owns all committed/effective RBAC evidence, filters, pagination, and Inspect/Reconcile/Revoke actions.

`Credentials` presents Human and CI/CD issuance as symmetric peer forms. Credential Lifecycle is a canonical registry table with filters, pagination, validity, reconciliation state, lifecycle actions, and protected material-generation actions. Its action column uses labeled **Generate** and **Renew** controls when eligible; Suspended credentials expose **Resume** as the primary action, while Expired credentials expose **Renew**. Secondary **Suspend/Resume** and **Revoke** actions are in a labeled **More** native dialog outside the scrolling table, so the controls remain accessible on narrow viewports. Revoked credentials and read-only users have no actionable mutation controls; generation requires Active/Renewal Due, Ready reconciliation and a suitable target namespace. Destructive revocation is described explicitly before the final submit. Desktop layout follows the canonical table contract without unnecessary horizontal scrolling; narrow viewports may still use controlled table overflow. Routine registry/detail surfaces never render secret material. Explicit material generation opens a non-cacheable one-time view; KAORI does not persist the returned token or kubeconfig body.

`Namespace Access` is a derived non-secret read model presented as a canonical registry with Tenant/Environment/Credential filters and pagination.

All tabs reuse the Analytics-derived `components/content_tabs.html` server-link mode. Every tab retains a real URL fallback while HTMX replaces only the Tenant Workspace. Mutation routes return operators to the relevant section.

Tenant identity is immutable after creation in the normal operator workflow.

- **Create** — create the Tenant ownership boundary and initial environment.
- **Read** — Tenant Registry is the committed-state source for operator reads.
- **Update** — no inline Tenant identity update is exposed. Name/slug identity, cluster placement, provider authority, and reconciliation authority are intentionally locked.
- **Lifecycle removal** — #735 owns governed teardown. Tenant detail exposes asynchronous **Decommission** and preserves one ordered lifecycle: freeze new mutations → revoke access state → retire memberships/groups → remove admitted managed resources/namespaces → retire reservation/exposure state → provider verification → commit `decommissioned`.
- **Provider verification** — a successful provider `DELETE` request is not completion. Native Namespace teardown observes Kubernetes until absence and never strips finalizers automatically. Capsule teardown likewise commits completion only after the authoritative Capsule Tenant CR is verified absent.
- **Capsule authority** — baseline Capsule teardown is admitted only for **KAORI-created, Managed, healthy Capsule Tenant CRs with zero active namespace/access/credential/managed-resource residue**. The adapter validates KAORI ownership labels, Tenant generation, and provider UID before deleting the Capsule CR, then verifies absence. Adopted/foreign Capsule objects, degraded Capsule state, active namespaces, or other unsupported provider residue remain fail-closed; KAORI never falls back to Native deletion.
- **Historical identity** — decommission retains the historical Tenant row, evidence, memberships, grants, credentials, and correlation lineage. Re-creating the same cluster+slug creates the next Tenant generation rather than overwriting history.
- **Name and namespace reuse** — the same Tenant slug may exist independently on different clusters. After a Tenant is fully Decommissioned, the same cluster+slug may be recreated as the next Tenant generation. A previously managed namespace name may likewise be reused on the same cluster only after the earlier namespace generation is provider-verified Deprovisioned; active duplicates remain fail-closed.
- **Structural change** — when immutable identity or placement must change, use governed teardown + recreation rather than mutating the Tenant in place.

#734 still prohibits a database-only lifecycle flag change from being presented as provider decommission; the final lifecycle transition now occurs only after the #735 provider verification path succeeds.

### Native Release ownership marker alignment (#1126)

Provisioning and Allocation Cutover write `kaori.io/resource-profile`.
Native Release handoff treats this as KAORI-owned metadata, not a foreign
label; the same existing conditional UID/RV Patch and verified read-back
applies to `app.kubernetes.io/managed-by`, `kaori.io/tenant-id`,
`kaori.io/environment`, and legacy `kaori.io/tenant-generation` /
`kaori.io/profile-id` keys. No blanket removal of provider labels.
Resource specs, CPU/memory, quota, foreign labels such as
`environment=uat`, annotations, credentials and RBAC remain unchanged.
Handback requires clean successor-owned resources and removes only the
verified successor manager; it cannot approve retained KAORI markers.

For already `Released` / `Handback Verified` objects carrying the
old `kaori.io/resource-profile` residue, the source fix **does not**
retroactively remove live provider labels. Keep Discovery blocked until
a separately approved, provider-authoritative, auditable metadata
recovery with UID/RV CAS, read-back and new lineage evidence is admitted.
Do not manually edit labels, retry verified Handback or force Adopt.
No Kubernetes mutation or quality gates are authorized by this source
change; tests/CI/formal UAT remain HOLD.

### Read-only assessment of legacy Verified Handback residue (#1129)

Before designing any *separately authorized* provider cleanup for an
already Released and Handback Verified Native Tenant, the source-only
service
`assess_legacy_native_profile_residue_readonly(tenant_id=..., actor_user_id=...)`
in `app/kubernetes/tenant/native_residual_recovery_assessment.py`
allows an authorized Platform Admin to obtain a noncommitting advisory
assessment. It performs the existing explicit provider GET and
SelfSubjectReview/SelfSubjectAccessReview against the registered KAORI
TLS-verified cluster, correlates the historical dry-run/Released/Handback
AuditEvents and Namespace lineage, and checks the exact Namespace,
ResourceQuota and LimitRange UID/RV, resource specs and owner-neutral
provider metadata. It does **not** run during normal Registry/Discovery
GET and does not add a new button, endpoint or service job.

Old pre-#1126 `retained_metadata_sha256` receipts regarded
`kaori.io/resource-profile` as a foreign label. Verification must use
**that exact historical four-key marker projection** rather than applying
today's expanded marker allowlist to old evidence. If the original
provider hash, live metadata, committed profile identity, exact scope,
last Handback resourceVersion or authorized provider principal differs,
the assessor fails closed. Its candidate report never permits a patch,
re-adoption, status change or AuditEvent write.

This read-only assessment is **not recovery authorization**. The residual
provider Namespace/ResourceQuota labels on `tenant-uat-demo` remain
Blocked until the separate #1128 mutation design, authorized
independent approval, conditional PATCH/read-back and append-only new
evidence are explicitly accepted. Do not retry already verified Handback,
run `kubectl label` manually, rewrite historical receipts, or force Adopt.
Regression test files are authored; running gates or provider mutation
still requires lifting HOLD.

### Governed Native residual metadata recovery executor (#1128)

The positive #1129 `read_only_recovery_candidate` report (2/2 components)
does **not** authorize Kubernetes cleanup. A separate source-only
`native_residual_recovery_governance` and
`native_residual_recovery_executor` pair implements strict
Prepare / Independent Approval / Execute / Read-back boundaries under
the existing Platform Admin permissions. A and B must be distinct,
authenticated KAORI human operators. Plans and approvals are immutable,
bound to the exact original Release/Handback plan SHA, a fresh read-only
provider assessment digest, UID/RV and component scope; expired or
changed evidence refuses execution. Both plan and approval use the
existing AuditEvent store, and no provider patch is made before an
immutable `in_progress` execution receipt is written.

The #1132 integration registers a narrowly scoped, authenticated and
CSRF-protected Tenant Detail POST route (with no background job);
once independently approved and explicitly confirmed, it can
conditionally remove only the exact `kaori.io/resource-profile` label
on verified historical Namespace/ResourceQuota/LimitRange components.
Each patch performs UID/RV/label-value tests, Kubernetes dry-run,
prewrite GET and postwrite read-back. The original CPU/memory, quotas,
RBAC, immutable metadata, external labels and annotations remain
unchanged; no wildcard KAORI label deletion. A failed partial patch
blocks automatic retries and demands fresh human provider recovery.

A complete recovery appends a new terminal AuditEvent and
`residual_recovery_governance` RV ledger; the prior verified Release
and Handback evidence remains untouched. Re-adoption still requires
fresh Discovery, provider preflight and next-generation authority.
For a newer RV, the existing lineage guard additionally checks
the *latest verified immutable recovery receipt* and checksum before
allowing another adopted generation. It never accepts a DB flag alone.
No cleanup, UAT, Developer Check, CI/CD or other quality gate has been
run or authorized; the presence of a new execution route **does not
lift the Kubernetes provider-mutation HOLD**. Human security review and
explicit authorization are required before pressing Execute or calling
the service directly in DevContainer.

### Native historical recovery UI → Discovery/Re-adopt (#1132)

In Tenant Registry select the **Released Native Tenant** and open
**Platform Admin Handback & Re-adopt**. A verified Handback with a
remaining Resource Profile label exposes **Historical Namespace Recovery**.
The status is projected from committed KAORI AuditEvent records only.
First use **Check Discovery First**; if already eligible, proceed with
normal Review Adoption and do not run recovery. Only a residue-induced
Discovery Blocked state warrants the recovery flow:
`Recovery Check · If Blocked`, `Pending Independent Review`,
`Approved — Not Executed`, `Recovery Review Required`, or
`Recovery Verified`. This section never scans Kubernetes on page GET.

The workflow uses exactly four existing-authority HTMX POST actions:
**Assess Live Provider Residue (read-only)** (shows a toast and does
not commit approval); **Prepare Governed Recovery Plan** (requester A
with a change reference); **Independently Approve Recovery Plan**
(Platform Admin B, different authenticated identity, plan SHA checked);
and **Execute Verified Metadata Recovery** (the same B with explicit
confirmation, fresh provider checks and UID/RV/label CAS dry-run,
conditional PATCH and complete read-back). Every request checks
`tenant.manage`, `integrations.manage`, `clusters.manage`,
CSRF and authenticated user; the business services still require
the unchanged historical release/Handback evidence and independent
approval. Locked/expired, completed, partial, and unknown states fail
closed with no retry. Controls use the existing Violet status, loading,
toast, checkbox and keyboard-focus conventions.

After `Recovery Verified`, use **Open Discovery & Review Adoption**.
This only navigates to the already approved Discovery preflight. A
fresh provider discovery must show the Namespace as ungoverned and
`Discovered`, with the original UID, no residual `kaori.io/*`
ownership label and the verified new RV ledger. The operator must
explicitly submit a new **Adopt & Manage** generation. Do not equate
a successful metadata cleanup to successful Re-adoption; no silent
takeover, quota/spec changes, or automatic Adopt are made.

**HOLD:** UI and backend source integration into
`kaori/review/staging-uat` is not live recovery evidence. Do not
press Execute, change provider resources manually, or Re-adopt
until independent human security acceptance, a deliberate provider
mutation authorization and the agreed gate/UAT release. Any expired
plan or in-progress/partial attempt requires new human
recovery governance, not replay.

### Provider Discovery and Adoption

#736 owns the two-way Tenant Registry path. Discovery is an explicit live-provider exception to normal committed-state reads: it reads Native Kubernetes namespaces and Capsule Tenant CRs on the Discovery request, shows provider status, correlates objects already governed by KAORI, and classifies candidates as **Managed**, **Discovered**, or **Blocked**. It does not wait for the Overview inventory worker sync. Discovery itself never mutates provider state.

Discovery intentionally keeps the registry pass lightweight. The registry request enumerates provider candidates only; it does **not** inspect per-candidate ResourceQuota, LimitRange, Capsule allocation authority, GlobalResourceQuota, or Capsule CRD capability state. **Review Adoption** lazy-loads one deep live Adoption Preflight through HTMX for the selected candidate. The preflight request builds detailed allocation/capability evidence only for that candidate. **Adopt & Manage** performs its own fresh provider read and fail-closed conflict/authority revalidation; preflight output is never trusted as mutation authority.

Manual provider deletion is treated as drift, not implicit Tenant deletion. After a fresh Kubernetes Inventory collection, `kubernetes.tenant.sync` marks a previously Ready managed/adopted Namespace as **Drifted** only when the inventory cutoff is at least as new as the Namespace's last KAORI-side provider evidence. The observation path never recreates or deletes resources automatically. **Operations → Drift & Reconcile** exposes corrective provider actions only through the admitted authority and explicit operator intent.

Explicit adoption is a separate human-confirmed mutation over KAORI committed state. The Adoption Preflight shows provider identity, live status, provider authority, current ownership, proposed KAORI mapping, governance checks, and the observed allocation baseline. Under the #777 human-reviewed contract, adoption uses a **provider-equivalent managed takeover**: observe first, materialize the supported values into committed KAORI control state, write the same effective values only through the authoritative provider path, then require provider read-back before control becomes Managed.

Native namespace adoption keeps Namespace lifecycle ownership **Adopted**. It captures ResourceQuota, Container LimitRange, and PVC Min/Max evidence, materializes the supported allocation contract, runs capacity admission, reconciles equivalent values through the Native authority, and records `allocation_control_state=kaori_managed` only after verified read-back. Namespace lifecycle ownership stays Adopted; allocation governance is an independent control dimension.

Capsule adoption keeps Capsule as execution authority. Admitted shared allocation can enter KAORI Managed control through the capability-gated Capsule path. Capsule-generated per-Namespace Container/PVC policy without an approved source-write contract is imported as `provider_mirrored_policy` and refreshed from provider authority so controller-owned values do not create false drift. Ambiguous, unsupported, stale, or capability-missing controls fail adoption closed rather than entering a partial managed state.

Observation evidence still records `provenance=adopted_observed` and `provider_mutation_performed=false` before takeover. Successful managed takeover records the authoritative mutation/read-back evidence separately. Adoption never silently converts provider principals into KAORI Membership/Access Grants and never bypasses provider authority.

### Managed Adoption and Legacy Allocation Governance Cutover

#777 is the current contract for new human-confirmed adoption. Existing **Adopted / Observed** records created under the earlier #768 behavior remain valid historical state and continue to use the #769 explicit allocation-control transition when an operator chooses to govern them:

```text
Adopted Namespace
└── allocation: Adopted / Observed
      ↓ explicit governed takeover
    KAORI Managed allocation
```

The takeover is available only when allocation authority is proven and supported. It compares current observed state with the intended Resource Profile, runs #654 capacity admission, revalidates provider UID/resourceVersion and ownership, performs only the authoritative provider mutation, then requires provider read-back before committing managed allocation state.

For Native Kubernetes, KAORI adopts control of the single authoritative ResourceQuota / Container LimitRange without taking Namespace lifecycle ownership. Existing legacy resource names are preserved when safely identifiable. Missing allocation resources may be materialized using the canonical KAORI resource names. Foreign-manager resources, multiple competing sources, unsupported LimitRange semantics, stale provider evidence, or read-back mismatch fail closed.

For Capsule, #771 admits one explicit shared allocation path: exactly one authoritative `GlobalResourceQuota` with healthy Capsule reconciliation authority, served v1beta2 API, and committed `shared_global_quota=available` capability evidence. The cutover uses the existing #124 CustomObjects executor, preserves the provider selectors and identity, performs shared Tenant-level capacity admission, verifies UID/resourceVersion before mutation, and requires provider read-back before the allocation becomes **KAORI Managed**. The shared quota is counted once for the Tenant rather than once per correlated Namespace. `Tenant.spec.resourceQuotas` and ambiguous/unsupported Capsule authority remain **Control Unavailable**. KAORI never bypasses Capsule authority with a direct Native quota write.

After successful cutover, normal governed allocation changes can operate on that allocation contract while the Namespace itself remains `ownership_status=adopted`. A provider failure before verification preserves the prior allocation-control state and records failure evidence for later drift/reconciliation review.

Tenant workspace mutations that are progressively enhanced with HTMX render operational feedback as an out-of-band KAORI toast in the same response. Success and failure feedback therefore appears immediately without requiring a full-page reload; persisted Notification Deck evidence remains synchronized through the standard toast notification-refresh contract.

The former monolithic UAT-only Members & Access and Credential Management partials are retired. Final UX does not expose `Functional UAT Surface` copy or render all administration forms simultaneously.

## Access and credential boundary

KAORI application RBAC (`tenant.view`, `tenant.manage`) is separate from Tenant Kubernetes Membership and Access Grant authorization.

The routine UI may show non-secret access metadata such as:

- Tenant/environment/namespace and cluster identity;
- Access Profile/version;
- approved access method;
- ServiceAccount name;
- lifecycle/reconciliation state;
- renewal/review and validity times;
- rotate/suspend/resume/revoke actions.

Routine Tenant inventory, registry, detail, report, Activity, and Namespace Access surfaces must never render bearer tokens, generated kubeconfig content, certificate/private-key material, or registry Secret material.

Explicit credential delivery is the bounded exception. An authorized operator may request one-time material from an Active/Ready credential and target Namespace. KAORI uses Kubernetes TokenRequest-backed ServiceAccount material, returns it only in a non-cacheable one-time response, records issuance metadata without plaintext secret content, and does not persist the token or generated kubeconfig body.

Material lifetime is independent from the longer credential entitlement/review lifecycle. Current KAORI policy offers operator-selectable lifetimes bounded by target environment: **Development up to 24 hours**, **Staging up to 8 hours**, and **Production up to 1 hour**. Kubernetes remains authoritative for the actual expiration timestamp and may return a shorter lifetime than requested.

Human access issuance uses the admitted #115 service and binds an individually owned reconciled User Access Grant to a non-secret JumpServer reference. The one-time Human action mints a ServiceAccount token for manual placement into the referenced JumpServer credential until direct JumpServer integration exists. CI/CD issuance uses the admitted #116 Deployer service and creates a namespace-scoped machine principal/grant/credential lineage. Its one-time action returns both kubeconfig YAML and a Base64 representation suitable for short-lived GitHub Actions UAT; long-running recurring delivery should later obtain fresh material at runtime rather than treating the governance entitlement as a static bearer-token lifetime.

Credential UI copy presents **Human Access Credential** and **Workload Deployment Credential** as separate capabilities; the issuance cards, registry delivery display, and material-request dialogs avoid using a single provider or CI/CD product as the generic feature name. **Access Account Reference** is presentation-only: it continues to submit the non-secret `jumpserver_reference` field and currently supports manual JumpServer token delivery under #115. Deployer issuance continues to submit the existing `github-actions-helm` purpose and short-lived kubeconfig delivery under #116. The registry displays a capability label without repeating vendor names; the authoritative delivery method remains preserved in the committed credential record and audit evidence. General wording must not be interpreted as support for additional access gateways, pipeline providers, or different credential mechanisms. Generated one-time material/result instructions are owned by #961. The result is a focused **transactional delivery page**, not a second Tenant inventory or administration workspace: it uses the existing Violet KAORI `page_hero` components with a short **Access Material** title and delivery context, while preserving its independent one-time response outside the ordinary Tenant onboarding gate. Navigation selects **Tenants** and displays the **Access Material** breadcrumb; other Tenant Heroes remain unchanged. The approved delivery context remains one full-width four-fact strip, followed by the warning before any exposed material. Context facts use a compact 14px value and 12px supporting-text hierarchy with responsive one/two/four-column layout; the long ServiceAccount identifier stays a single truncated line, exposing its complete value in the title and through the already-loaded KAORI clipboard control. This is presentation-only and does not change the canonical shared Resource Posture Grid or provider evidence. Human token or kubeconfig and Base64 appear in full-width canonical `one_time_secret.material_block()` surfaces, never as parallel sidebars. The three delivery steps use a horizontal row at desktop widths (stacked on smaller screens), and only Deployer material shows the full-width ephemeral kubeconfig command example. The right Hero panel ends with the standard **Back to Credentials** action; the compact footer keeps **distinct** entitlement validity and provider-issued material expiry without a duplicate navigation button. The Human token and Deployment kubeconfig result surfaces now use capability-first labels and manual-vs-automated delivery instructions rather than presenting JumpServer, GitHub Actions or Helm as universal requirements. Deployer results show automated-delivery steps and a temporary kubeconfig example with restrictive permissions, Kubernetes authorization verification, and file cleanup. Administrative/approved individual kubeconfig results instead show governed manual-use steps, never pipeline-only instructions. The result page reads entitlement validity from the committed access-package evidence rather than incorrectly repeating the short-lived token expiry. Actual Human delivery remains the existing manual JumpServer reference contract and automated delivery remains an exported ephemeral Kubernetes kubeconfig; this wording does not authorize additional provider integrations.

## Intelligence and reporting

Tenant does not own a second Intelligence engine or export subsystem.

- Tenant Governance findings are selected from the canonical Intelligence Recommendations authority using `kubernetes.tenant.*` rule keys.
- PDF, XLSX, and CSV publication is routed through the canonical Reports publication lifecycle from #655.
- Missing/stale evidence remains explicit; absence of provider/capacity evidence is never converted into a healthy or zero value.

## Final UAT boundary

Native-provider acceptance is mandatory. Final UAT must exercise, as applicable:

1. Expand/collapse the Tenant parent and verify Overview, Tenants, Resource Profiles, Namespace Provisioning, and Operations active states on desktop/mobile.
2. Tenant/environment creation.
3. Resource Profile and governed namespace provisioning.
4. Membership and Access Grant creation/revocation.
5. Human JumpServer credential issuance and lifecycle.
6. CI/CD Deployer identity issuance.
7. Namespace Access metadata without secret exposure.
8. Managed-resource, policy, provider-state, Activity, and Kubernetes audit evidence inspection.
9. Tenant Governance findings and capacity admission evidence.
10. Representative Tenant Governance PDF/XLSX/CSV generation and human artifact review.
11. Native Tenant decommission end-to-end: freeze mutations, revoke credentials/grants/memberships, remove managed state, observe each namespace absent (including a controlled Terminating/finalizer blocker case), verify final provider cleanup, and recreate the same cluster+slug as a new generation while historical evidence remains queryable.
12. Baseline Capsule decommission: create a KAORI-managed Capsule Tenant with no namespace/access/provider residue, request Decommission, verify the authoritative Capsule Tenant CR is deleted by Capsule authority and observed absent, then confirm the historical KAORI Tenant reaches Decommissioned. Also prove adopted/degraded/residue-bearing Capsule cases remain blocked.
13. Managed Namespace provider-loss recovery: delete a KAORI-managed Namespace directly in Kubernetes, confirm Discovery shows **Provider Missing**, collect fresh Inventory + run Tenant sync to commit **Drifted**, verify sync itself does not recreate anything, then use **Operations → Drift & Reconcile → Reconcile** to restore Namespace + ResourceQuota + LimitRange from committed intent.
14. Legacy Native allocation governance cutover: discover/adopt an existing Namespace with provider-owned ResourceQuota / LimitRange, verify **Adopted Baseline · Observed** preserves source UID/resourceVersion and has no KAORI desired hash, select a governed Resource Profile, prove capacity/ownership preflight, mutate through Native authority, read back the effective allocation, and only then verify allocation control becomes **KAORI Managed** while Namespace lifecycle ownership remains **Adopted**. Repeat with stale/out-of-band provider evidence and prove cutover fails closed without changing KAORI desired intent.
15. Legacy Capsule allocation cutover boundary: adopt a compatible Capsule Tenant and verify allocation authority is identified from admitted Capsule/native evidence. When no admitted Capsule mutation path exists, the UI remains **Control Unavailable** and KAORI performs no Native quota bypass.
16. Native managed-allocation drift: after a Native allocation is **KAORI Managed**, change ResourceQuota and/or Container LimitRange directly in Kubernetes while KAORI is not performing the mutation. Run Tenant Sync and verify the Namespace becomes **Drifted**, the last KAORI intent and current provider observation are both retained, dimension-level differences are visible, and sync performs no corrective provider write.
17. Bidirectional allocation recovery: use the reference legacy Tenant/project **API** with existing owner/principal **APE** after allocation control is KAORI Managed. Change the live allocation manually during a simulated KAORI outage, run Tenant Sync, then verify **Reapply KAORI Intent** uses the current live provider allocation as the capacity-preflight current state, rechecks provider freshness before mutation, writes through Native authority, and clears drift only after read-back verification. Repeat the scenario and verify **Accept Provider State** performs policy/capacity/ownership validation, performs no redundant provider write, commits the live values as new desired/effective intent with provenance, and clears drift. Change the provider again between sync and either action and prove the action fails closed as stale.
18. Capsule GlobalResourceQuota governance: adopt the reference **API / APE** Capsule Tenant with exactly one authoritative `GlobalResourceQuota`, healthy Capsule authority, served `capsule.clastix.io/v1beta2`, and committed `shared_global_quota=available`. Verify the shared quota is counted once across correlated Namespaces, Cut Over Governance mutates only the authoritative GlobalResourceQuota, provider UID/resourceVersion and selector/tenant correlation remain preserved, and provider read-back is required before the shared allocation becomes **KAORI Managed**.
19. Capsule shared-allocation drift: after GlobalResourceQuota governance is managed, change the GlobalResourceQuota directly during a simulated KAORI outage, run Tenant Sync, and verify committed **Drifted** evidence retains KAORI intent plus provider observation. Prove **Reapply KAORI Intent** and **Accept Provider State** both use Capsule authority, apply shared-capacity admission, reject stale provider observations, and never write namespaced Native ResourceQuota as a substitute.
20. Capsule GlobalResourceQuota unsupported-authority boundary: repeat adoption with multiple/ambiguous GlobalResourceQuota sources, degraded `shared_global_quota`, unsupported selectors/dimensions, or an unsupported served API version. Verify the allocation remains **Control Unavailable**, no provider mutation occurs, and the reason is explicit.
21. Legacy Capsule Tenant quota — **estimasi** case: discover/adopt an existing Capsule Tenant whose authoritative allocation is `Tenant.spec.resourceQuotas` with no proven Namespace correlation and `scope=Tenant`. Verify Adoption Preflight is decision-first: **Adoption Decision**, **Adoption Impact**, **Allocation Overview**, **Namespace Coverage**, and **Technical Evidence** make the read-only boundary explicit. The primary action is **Adopt as Observed** and must state **No provider mutation**. **Observed · Read Only** is shown only when the live served Tenant CRD schema proves `spec.resourceQuotas` and the capability is available. Adopt without provider mutation, then perform explicit governance cutover, capacity admission, Tenant CR resourceVersion check, patch only `spec.resourceQuotas`, provider read-back, and confirm allocation becomes **KAORI Managed** while Tenant ownership remains **Adopted**.
22. Legacy Capsule Tenant quota — **partner** case: adopt a Tenant with correlated Namespace `partner-pgnpartner-development`, authoritative `Tenant.spec.resourceQuotas`, and a Capsule-generated `PersistentVolumeClaim` LimitRange. Verify KAORI maps the PVC LimitRange as a known **PVC Storage Constraint** with Namespace, LimitRange identity, provider UID/resourceVersion, and supported storage min/max evidence when present. It must appear under **Provider Constraints** as **Observed · Preserved**, must not be reported as a raw unsupported `type=PersistentVolumeClaim`, must not become Tenant-quota authority, and must remain untouched while the admitted Tenant quota is cut over and later changed through KAORI.
23. Capsule Tenant quota bidirectional recovery: after #773 allocation control is **KAORI Managed**, change `Tenant.spec.resourceQuotas` directly during a simulated KAORI outage. Run Tenant Sync and prove it performs no write, commits **Drifted** evidence with desired/provider values plus Tenant UID/resourceVersion, then exercise **Reapply KAORI Intent** and **Accept Provider State** separately. Reapply must use fresh live allocation for capacity admission and require provider read-back; Accept must perform no provider write and commit the live quota/scope with `provenance=accepted_provider_state`. Change the Tenant CR again between Sync and either action and prove stale resourceVersion/hash fails closed.
24. Capsule Tenant quota safety boundaries: prove non-empty `scopes` / `scopeSelector`, unsupported authoritative hard dimensions, ambiguous duplicated quota dimensions, competing allocation authority, degraded Capsule, missing `spec.resourceQuotas` CRD schema, and incompatible API versions remain **Control Unavailable**. No path may fall back to namespaced Native ResourceQuota mutation.
25. Discovery performance boundary: open, filter, and paginate **Tenant Discovery** and verify the registry performs candidate enumeration only; ResourceQuota/LimitRange, Capsule allocation authority, GlobalResourceQuota, and Capsule CRD capability inspection must not run per visible row. Click **Review Adoption** and verify exactly that selected candidate receives the deep live HTMX preflight, with a visible fail-closed error state if revalidation fails. Submit **Adopt as Observed** and verify adoption performs a new live provider/conflict revalidation instead of trusting the preflight response.
26. Offline committed-read boundary: complete at least one Tenant sync, record the committed snapshot cutoff/coverage, then make the Kubernetes API unreachable. Open **Tenants**, **Resource Profiles**, **Namespace Provisioning**, and **Operations** and verify committed KAORI content still renders immediately. **Tenant Collection Snapshot** must retain the last committed evidence, any explicit Live Provider Connectivity probe (via its existing supported endpoint) must report its own reachability state, independent of the committed snapshot; child pages must have no probe panel or action, Resource Profile/capacity committed evidence must remain visible for registered clusters, and provider-backed mutations must continue to fail closed. Repeat with no successful Tenant sync and prove **Not Collected** is distinct from provider connectivity failure.
27. Light/dark, responsive, loading/empty/error/degraded, keyboard/focus, and normal KAORI not-found behavior for unsupported Tenant URLs.

Capsule UAT is capability-conditional and must record the exact compatible Capsule evidence when available. Fixture-only Capsule state is not acceptance evidence.

Promotion to `main` is outside this issue. Accepted Tenant work remains in `kaori/staging` until the governed release/promotion flow.
