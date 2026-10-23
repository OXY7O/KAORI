# Access Domain

## Purpose

`app/access` owns the administrative Access control-plane presentation and HTTP orchestration for cross-cutting identity and authorization workspaces. It does not own authentication protocols, user persistence, or RBAC policy evaluation.

Canonical landing page:

```text
/access/
```

Current navigation composition:

```text
Access
├── Overview
├── User Management
├── Identity Providers
├── Roles & Access
├── Permission Catalog
└── Activity Audit
```

## Ownership boundary

- `app/access/overview/` owns the read-only Access landing page.
- `app/access/roles/` owns role-management HTTP routes, forms, presentation context, and role mutation orchestration.
- `app/access/permissions/` owns the read-only Permission Catalog HTTP/presentation boundary.
- `app/access/activity_audit/` owns the system-wide Activity Audit HTTP/workspace boundary.
- `app/access/users/` remains authoritative for user lifecycle and effective-access presentation.
- `app/access/identity_providers/` owns Identity Provider administration and directory projection workflows.
- `app/access/authentication/identity_provider/` owns provider catalog, adapter registries, protocol validation, and external authentication contracts.
- `app/access/authentication/` owns session admission and authentication orchestration.
- `app/access/rbac/` remains authoritative for the code-owned permission registry, protected default roles, authorization rules, role mutation guardrails, and route decorators.
- `app/platform_operations/notifications/` remains authoritative for Notification Center persistence and the shared operational evidence store/query kernel. Activity Audit presentation and HTTP orchestration belong to `app/access/activity_audit/`.

The Access menu groups these capabilities; it does not duplicate their domain logic.

## URL ownership

Canonical Access-owned URLs:

```text
/access/
/access/roles/
/access/roles/new
/access/roles/<id>
/access/roles/<id>/clone
/access/roles/<id>/edit
/access/roles/<id>/delete
/access/permissions/
/access/activity-audit/
/access/activity-audit/<notification-id>/details
```

User lifecycle remains under `/users/`. Identity Provider administration is canonical under `/access/identity-providers/`; no compatibility route is retained under `/users/providers`.

Legacy Settings role/permission URLs are retired. Settings must not contain redirect shims, compatibility wrappers, or role/permission presentation/mutation logic; callers must use the canonical Access routes.

## Final lock boundary

Access v1 is final-locked across Access Overview, User Management, Identity Providers, Roles & Access, Permission Catalog, and Activity Audit. Runtime ownership remains distributed by domain, while the Access control-plane UI, security boundaries, canonical components, and legacy-cleanup rules are protected by `scripts/verify_access_final_lock.py`.

## Access workspace section introductions

The Permission Catalog, Roles & Access, and User Management pages use the existing `components/section_intro.html` outside the owned card to establish the next section's purpose. Permission Governance introduces the shared Permission Registry / Role Coverage tab workspace; Authorization Flow and Role Administration introduce their separate role-flow and registry cards; Account Directory introduces User Directory. Card-owned titles, search/filters, actions, status, pagination and permission-scoped data remain unchanged. HTMX swaps continue targeting only `permission-workspace` and `user-directory`; the outer section intro is not rendered inside those fragment targets. No new component or layout system is introduced.

## Access Overview review status

Access Overview is a read-only composition surface. It does not query User, Identity Provider, Role, Permission, or Activity persistence directly to invent a second health model. The overview consumes domain-owned summary contracts and only aggregates permission-scoped posture. Roles and Permission Catalog expose summary-only projections for Overview; the full registry/detail builders remain authoritative for their own workspaces, while the common summary calculators preserve identical aggregate counts and drift semantics. These request-time projections read KAORI's committed DB state and make no external-provider calls.

The aggregate Access posture follows the approved `Critical > Warning > Info > Unknown > Normal` precedence across **visible, permission-scoped** workspaces. An optional, unconfigured provider or an empty visible scope is not labeled `Current / Normal`; neither is it turned into a failure. Domain-owned statuses remain authoritative, and Activity Audit event counts remain evidence rather than health signals.

The posture contract now treats missing active break-glass authority, active users without role assignment, inactive roles with assigned users, permission-registry drift and enabled identity-provider configuration/admission-policy gaps as explicit review signals. Activity Audit warning/error records remain evidence counts and do not make the audit workspace itself unhealthy. On Access Overview, the 24-hour event/actor/attention counters refer only to the Notification-backed Activity Register, not to source-owned `AuditEvent`, Tenant or Job evidence or archived history. Zero attention in that store must not be presented as absence of all administrative evidence. Optional external authentication remains informational when no provider is configured.

The Hero left metadata communicates domain-owned composition, permission scope and committed evidence; the right context metrics alone report the visible Workspace and Review counts. Workspace card metric labels wrap without hover-only tooltips, stack as a readable list on phones, and retain a three-column comparison from the tablet breakpoint. Mobile cards do not enforce a desktop minimum-height floor. Responsive/keyboard/light-dark/zoom Visual QA remains required in DevContainer before human acceptance.

Control Boundaries expose the same authoritative posture as their source workspace instead of static architecture copy alone. This composition rule is protected by `scripts/verify_access_final_lock.py`.

## Administrative Evidence — Job archive handoff

Administrative Evidence remains a permission-scoped hot `AuditEvent` source. `Open Job` appears only when `jobs.view` is granted and the referenced `JobExecution.public_id` exists in the live registry. When the job is absent, readers granted **both** `jobs.view` and `platform_operations.view_data_lifecycle` may **Browse Job Archives** in Data Lifecycle → Archive History filtered to `job_execution`; the UI explicitly states that this is an archive-bundle browser and **does not verify whether the job is archived**. Without lifecycle access the action says **Job unavailable**; non-job records retain **Source-owned**. The presentation batches the lookup across one paginated AuditEvent page; it does not scan compressed archives, reconstruct identity from actor FK, or expand permission grants. Verified single-job archive deep links need a separate immutable correlation index and permissioned reader.

## Activity Audit detail review status

Activity Audit Detail remains a **read-only, content-driven shared resource modal** over the Notification-backed Activity Register, not a consolidated audit store or new authority. The recorded status, title, immutable actor snapshot, target, category, timestamp, and sanitized metadata remain authoritative. The first content section for warning/error events emphasizes the **recorded outcome**, followed by recorded failure-context fields when present; the original message is retained as a separate impact note where distinct. The UI **does not infer a list of blockers from a freeform count** or claim unseen provider changes/root causes. Without failure-context fields, it says so and points readers to trace and permissioned committed source links; next-step copy is review guidance, not operational authorization.

Execution evidence, recorded changes, related committed evidence and trace references remain visible and source-owned. The Activity Audit modal now renders the actor/target/recorded/evidence summary **inside the same fetched modal header as its title and badges**, rather than a second card in the modal body; the shared `summary_strip` keeps the existing opt-in `layout='unified'` geometry with a flat, one-surface, divider-only presentation. The separate pinned summary host remains unused for this detail. The modal header is still bounded by the existing shell, so long names must be checked at mobile, zoom and reduced height before UAT acceptance. Other shared summary variants retain their established behavior.

The Activity Audit overview now uses shorter metric and evidence-boundary descriptions without changing the Notification-backed data scope. Audit Context follows the same two-column, separated definition-list rhythm as Trace References: Actor & Access and Target Context retain named groups, left-aligned labels and values, and wrapping for long identifiers. Trace References now uses the Violet section-icon treatment consistently with Audit Context. Additional Evidence remains a responsive, two-column metadata list in the existing collapsed View More; Technical Evidence retains its disclosure. No serializer, actor, status, security, source authority, provider query or mutation behavior changes; the same committed record is displayed.

Regression source contracts exist; DevContainer keyboard, focus/scroll, mobile, 200% zoom and light/dark Visual QA are required before human acceptance.

## Roles & Access review status

Roles & Access uses the KAORI operational registry pattern: read-only posture overview, compact assignment flow, full-width filtered Role Registry, expandable role evidence, and a sticky impact rail on role forms. Role Registry now delegates its search/type/state filters, Clear Filters, Rows, pagination, latest-request-wins HTMX synchronization, and GET fallback to the canonical `table_registry` shared components, including exclusion of a duplicate hidden `per_page` value from the Rows form. The old page-local Role-Permission Mapping Matrix and `role_access_tabs.js` have been removed; cross-role permission coverage belongs to Permission Catalog.

Custom-role edit/delete mutations are serialized with a database row lock and protected by a role version token so stale administrative forms do not silently overwrite a newer role state. Create and clone now explicitly roll back SQLAlchemy/transaction failures (including concurrent unique-slug collisions), show a recoverable form error, and issue failure feedback rather than surfacing an unhandled request error. Delete blockers for user assignments and Identity Provider defaults are rechecked at mutation time.

Inactive custom roles remain administratively recoverable: assignment and cloning eligibility require active roles, while authorized role edit/reactivation/delete checks use a separate management ceiling independent of the target role's active flag. Protected defaults stay immutable, and stale-version, deactivation acknowledgement, and user/provider deletion blockers remain authoritative.

Role Configuration shows a checkbox-derived Active/Inactive assignment badge, using *on save* wording for unsaved create/edit/clone changes. The existing role form JavaScript synchronizes both the form badge and Role Impact badge as the checkbox is toggled; read-only mode shows the committed state.

The role mutation boundary also enforces a delegation boundary: a non-break-glass role manager can only grant permissions already present in their own effective role. Protected default keys remain source-controlled even if database `is_system` metadata drifts, and Roles & Access surfaces baseline drift until explicit `flask seed-rbac` convergence. Administrator-level role classification is capability-based from the RBAC catalog rather than the role slug. Deactivating a referenced custom role requires explicit impact acknowledgement.

Role Detail remains an existing content-driven shared modal with the canonical header and borderless four-fact summary (assigned users, provider defaults, assignment availability, and effective permissions). Its body uses **one existing `resource_sheet`** and four compact `inventory_section` bands—Role Identity, Assignment Impact, Permission Coverage, and Administrative Boundary—rather than cramped equal-width cards. Long Operational Purpose, Baseline Evidence, Authorization Effect and administrative ownership messages receive full-width, normal-weight reading rows; only short facts use responsive grids. Permission Coverage is an accessible module directory: each module first displays its title, key, and permission count, followed by a full-width **Capabilities** row containing every effective capability label (including a single `View`/`Sync`/`Manage` permission). This stacked structure avoids the former responsive side-column that could place labels outside the immediately visible area on narrow screens; no permission is hidden behind disclosure or pagination. Administrative actions appear beneath full-width governance context and retain the original permission checks, delete confirmation, CSRF and role version token. No new modal host, provider request, RBAC authority or destructive-action semantics are introduced. The Roles overview explains that inactive roles fail closed on the next **effective** authorization check and shortens baseline drift copy to **Protected defaults require RBAC review.**

This Roles & Access presentation is part of Access Final Lock v1. RBAC seed/convergence remains an explicit deployment boundary owned by the Permission Catalog and `flask seed-rbac`.

## Permission Catalog review status

The permission **Active Usage** projection counts unique active users only through **active mapped roles**, consistent with the inactive-role denial enforced by `User.has_permission()`. Permission role-mapping counts retain inactive roles as mapping evidence. Enabled JIT provider defaults remain separate configuration evidence, not proof of active effective user access. The registry and detail label this projection **Effective Users** and **No Effective Users**, not all users assigned to a role or break-glass authority.

Permission Registry and Role Coverage use the existing `table_registry.filter_form`, `clear_filters_link`, and `footer` interaction contract against the server-owned `#permission-workspace` response. Filter changes reset to page 1; the shared HTMX latest-request-wins synchronization, GET fallback, push-history, loading indication, Clear Filters, numeric pagination, and Rows 5/10/25/50 remain canonical. The Rows form excludes a duplicate hidden `per_page` value so the selected size is authoritative. No local JavaScript is added.


Permission Catalog is a read-only Access workspace. HTTP GET routes no longer call `seed_default_rbac()` or perform RBAC convergence. Code-to-database alignment is presented as registry evidence (`Canonical`, `Missing From Registry`, `Metadata Drift`, or `Database Only`), while synchronization remains an explicit deployment/administrative step through `flask seed-rbac`.

The catalog owns two views:

- **Permission Registry** — code-owned contracts, dependencies, current role mapping count, registry drift, shared filters/loading, and standard pagination.
- **Role Coverage** — cross-role effective permission comparison. Roles & Access intentionally keeps only role-specific permission coverage in its detail modal. If role filters match no roles, the table renders a named Role Coverage fallback column aligned to its explanation cells, with a consistent empty-result colspan and a narrower table minimum; populated role matrices retain their normal columns and sticky identity. Within the Role Coverage permission identity cell, the delegation-tier badge is rendered as optional supporting content of the existing shared `table_ui.title_cell`, aligned with the permission title and key rather than underneath the icon. The optional shared slot preserves the original title-cell presentation for other callers.

The two framed Permission Registry / Role Coverage tabs carry no record-count badges. The read-only permission detail retains the shared content-driven modal and committed RBAC evidence, using a balanced four-fact semantic summary (role mapping, active usage, enabled JIT default projection, transitive dependencies) rather than displaying raw counts. The Permission Detail modal uses the existing **single unified resource sheet** and shared **inventory section bands**: Permission Identity, Dependency Contract, Delegation Boundary, Registry Boundary, and Role Coverage. On wider viewports, each band has a quiet left identity rail and a wider evidence panel; on narrow screens they stack naturally. The Permission Detail alone opts into compact shared section padding and concise rail descriptions, with short identity/dependency facts aligned, delegation Authority aligned with the same evidence-column edge as other detail facts (without an extra inset or nested Violet rule), registry read-boundary text at legible body size, and a narrower table minimum that scrolls only when needed. Other shared resource sheets retain their default density. This replaces five individually bordered cards and their repeated heading/padding without changing modal behavior. The compact four-fact summary remains nonnumeric and uses the existing shared `summary_strip(borderless=true)` variant: evenly spaced status facts without vertical cell dividers or separate card borders. Other shared summary callers retain their previous styling by default. Descriptions are removed from the Permission summary to avoid repeating the evidence below. Short identity facts use a responsive inner grid, while long delegation/registry text keeps a comfortable reading width. Role Coverage stays within the same sheet and retains exact role/state/type evidence while showing usage and JIT presence; absent JIT paths must not be characterized as an identity provider being globally disabled. This is presentation-only: authorization, dependency closure, role/user/JIT counts, and governed RBAC recovery remain authoritative in their existing sources.

This Permission Catalog presentation is part of Access Final Lock v1.


## Activity Audit review status

Activity Audit is an Access-owned, read-only evidence workspace over the shared `notifications` operational evidence store. The hot register uses persisted `category_key`, `actor_key`, `actor_label`, and immutable `actor_snapshot_json` fields rather than reconstructing actor identity from the current User row. Notification recipient ownership remains separate through `notifications.user_id`.

The register reads hot PostgreSQL rows only. The `All Hot Records` option is intentionally explicit; verified older evidence remains under Platform Operations → Data Lifecycle after archive-and-cleanup. Notification recipient deletion cannot erase retained evidence because the Notification foreign key uses `ON DELETE SET NULL`, while actor identity remains in the immutable snapshot.

Evidence scope is deliberately precise: Activity Audit lists persisted `notifications` activity, including audit-only rows hidden from Notification Center. It does **not** silently union `audit_events` administrative/Tenant lifecycle records, `tenant_audit_evidence` Kubernetes correlation records, or `JobExecution` records. Those evidence owners retain their own read, authorization, lifecycle and correlation contracts. Future cross-domain correlation must be a governed workstream; the Activity Audit UI must not imply universal coverage just because the reader has system-wide permissions.


### Source-linked Activity Audit detail (issue #1219)

For currently committed Notification records, related links appear only after domain-specific permission and exact source lookup. Jobs requires `jobs.view`; Tenant governance requires `tenant.view` or `tenant.manage` and a matching `TenantAuditEvidence`/Tenant association. Links navigate source-owned workspaces; no new audit entries, fabricated actor snapshots, unauthorized source details, or archive continuity are implied. Administrative-only AuditEvent coverage remains governed by #1219 and parent #1208.


### Source-linked outbound delivery journal (issue #1220)

Notification Channels' existing **Delivery Activity** table can be narrowed by an **exact committed event key** via a normal GET or HTMX workspace refresh; the filter is retained on pagination. Activity Audit may link to this journal only when its own committed Notification metadata explicitly provides `event_key`/`delivery_event_key`, a matching `NotificationDelivery` exists, and the actor has `integrations.manage`. A channel fan-out, retry, duplicate suppression, or `NotificationEvent` dispatch is not an additional authored KAORI business-action audit event. Report and Automation Control actions that have no Notification record are **not** manufactured or silently bridged by this view.


### Administrative-only committed audit sources (issue #1219)

A distinct **Administrative Source Evidence** section is available on the Access Activity Audit page for readers with `activity_audit.view` and source-specific `jobs.view` (automatic Job AuditEvent) or `tenant.manage` (Tenant inventory synchronization AuditEvent). This is a separate, explicitly labeled hot AuditEvent query, not a union with the Notification Activity Register. It uses canonical server pagination (5), source allowlists, HTMX GET/fallback and a bounded presentation of action/summary/timestamp. `AuditEvent.actor_user_id` is a nullable FK reference, **not** a snapshotted actor identity: the UI must not infer user role, authentication source or actor at commit from it. Only exact existing `JobExecution` records are linked and only when `jobs.view` is granted. No raw metadata, Native handoff approval payloads, provider calls, archive continuity or duplication/backfill is introduced by this slice.


### Audit Records tab hierarchy (issue #1237)

Below **Audit Evidence Overview**, Activity Audit now uses the shared Inventory `section_intro` hierarchy for **Audit Records** and canonical `content_tabs.render_links` navigation. The top-level **Activity Register** tab (default) and **Administrative Evidence** tab (only where the user holds `jobs.view` or `tenant.manage`) show **one** independent table at a time; they do not combine their counts, actors, source authorization or retention. Activity Register keeps its HTMX filters, existing Notification-backed detail modal, snapshot actor attribution, and archived Data Lifecycle history. Administrative Evidence retains hot-only AuditEvent source scope, separate permissions, 5-row pagination and explicit actor-FK semantics; Automatic Jobs/Tenant Inventory Sync are a source-scope select rather than another tab bar. Both work via URL-backed GET, progressive HTMX and history restore. The administrative action uses the canonical operation label only when a matching committed JobExecution is available and `jobs.view` permits access; otherwise it retains the event-derived fallback. The original recorded action key remains visible as supporting evidence. Source and nullable actor FK provenance share one compact column; neither establishes a human actor snapshot. No source records or producers change.


### Framed Audit Records and administrative filters (#1237, DevContainer feedback)

Audit Records uses the existing **server-framed workspace tabs** aligned with Tenant Workspace. Administrative Source Evidence uses the same shared `table_registry.filter_form` and `table_registry.footer` interaction contract as other registries, with Search Activity (action/summary/target reference, bounded to 120 characters), Source Scope, Outcome, Recorded Time (All Hot Records, 24h/7d/30d/90d), conditional **Clear Filters**, canonical empty state and 5/10/25/50 Rows. Its loading bar is rendered below the header title/action row in a full-width block (matching Activity Register), not as a sibling within a responsive horizontal flex header. The shared filter form retains an accessible name and stable element ID. Clear Filters resets all filters and page to 1 **while preserving Rows**, matching the existing registry convention. GET/HTMX, source permissions, Actor FK labeling, hot-only AuditEvent evidence and the Notification-backed Activity Register remain independent. The footer disclaimer has been removed from the UI; its underlying governance remains documented.

## Identity Providers Overview and records workspace

Identity Providers uses the **same approved read-only information hierarchy as Access → Activity Audit**: the full-page Hero is followed by a single Authentication Source Posture panel containing the committed **Configured, Enabled, Directory, and Browser SSO** metrics and four authoritative **Identity Governance** boundaries in the same surface. The overview uses the existing Audit Evidence Overview structure, responsive 4/2/1 metric columns, and four boundary tiles. The optional, long explanatory posture footer is deliberately omitted for visual density; configuration completeness is **not** a verified Test Connection, and zero optional external providers does not imply failure of separate Local Database authentication. Governance tile descriptions and form guidance stay concise while preserving provider/adapter authority, external secret ownership, linked identity projection and KAORI RBAC boundaries.

Below the persistent overview, a single **Identity Provider Records** workspace uses canonical server-owned `framed_workspace_tabs.render_navigation` (like Activity Register) with **Provider Registry** and **Directory Provisioning** as tabs. `?tab=providers` is the default, while `?tab=directory` shows committed directory sources, identity-link counts and local KAORI Roles authorization ownership. The previously supported `?tab=overview` falls back to the default registry without losing the always-visible posture panel. The directory tab contains a separate **Open Directory Provisioning** link, visible only to `identity_providers.provision` actors; the real signed-proof, CSRF-bound provisioning workflow continues at its existing page, not inside an ungoverned overview form. View-only users see read-only context instead of a privileged action.

The HTMX boundary is intentionally split: tab navigation targets **`#identity-provider-workspace`**, returning its full tab wrapper, while canonical Provider Registry filters/Rows/pagination target **`#identity-provider-registry`** and return only registry content **with `embedded=True`**. The parent workspace alone owns the border, rounded corners and shadow, including after filtering, clearing filters, changing Rows or paginating; a standalone registry render retains its normal shared table frame. Both preserve normal GET links, browser history, canonical loading/empty/error behavior and permission-gated expandable details. No new JavaScript, provider request, secrets, RBAC policy, JIT logic, directory projection or external authority is introduced. DevContainer browser QA and explicit human acceptance remain pending; CI/CD and admission gates remain HOLD.

## Identity Providers canonical registry interaction

Identity Provider Registry delegates its provider/state/search filters, Clear Filters, Rows, pagination and latest-request-wins HTMX synchronization to the approved `table_registry` shared macros. Its `tab=providers` context is preserved on filter, clear and pagination; Rows uses one `per_page` input without a duplicated hidden value. Page size defaults to five and retains 5/10/25/50. Provider detail expansion, enabled/configuration evidence, permission-gated actions, URL history, loading and GET fallback remain unchanged.

## Identity Providers administrative mutation failure boundary

Provider Create/Edit retains server-side CSRF, form and delegation checks. Services roll back database write failures, while HTTP routes now translate non-duplicate SQLAlchemy failures into a sanitized, recoverable form error and standard operational failure notification. Duplicate instance keys retain their separate field error; unexpected SQL details stay in server logs only. This does not introduce persisted connection-health evidence or change provider enablement authority.

## Identity Providers JIT admission at configuration time

Controlled JIT always requires an **active non-administrator default role**, even when a Local Database Super Admin configures the provider. Create, Edit and Test Connection reuse the same input boundary, so an invalid default role cannot be saved as a seemingly valid JIT configuration. Normal role delegation remains authoritative for non-JIT administrative configuration; runtime admission continues to enforce the strict JIT policy independently.

## Identity Providers directory-projection transaction boundary

Directory search results are bound to a signed provider/actor projection proof. Creating the KAORI User, ExternalIdentityLink and AuditEvent occurs in a single caller-owned SQL transaction; any SQLAlchemy failure (including first user flush, identity-link flush and commit) rolls back the whole transaction and produces a sanitized failure notification. A failed projection cannot be treated as a partially provisioned identity or successful audit evidence. Runtime failure-injection remains a required DevContainer UAT scenario.

## Identity Providers linked-identity continuity

An existing Identity Provider with projected `ExternalIdentityLink` records cannot change its stable instance key (browser callback authority) or provider type/adapter on the same row. Its existing `provider_id + subject` mapping remains bound to the original external identity authority. Ordinary configuration edits under the same key/type remain allowed. To change identity authority, create a new provider and conduct separately authorized identity relinking; editing an existing linked row is not a migration mechanism.

## User Management role-recovery boundary

For User Edit GET and directory action visibility, manage authority is evaluated independently of an existing inactive/missing role so authorized administrators can repair stale assignments. POST always validates the **new active delegable role** and preserves administrator-level protection, self mutation constraints, Local Database break-glass and last-active-super-admin safeguards. Inactive roles never grant runtime effective permissions.

## User Edit stale-mutation protection

User Edit forms include a committed user-version token. A POST serializes the current User row using `SELECT ... FOR UPDATE` with refreshed persisted state and refuses stale tokens **before** modifying profile, role, administrative tier, or lifecycle or recording success evidence. The operator must reload the newest state before retrying. A last-active-local-Super-Admin demotion still acquires the existing specialized lock/guard first; self-modification and role delegation stay fail closed. This is administrative optimistic concurrency, not external-provider account synchronization.

## User lifecycle transaction recovery

Activate, Deactivate, Restore, Delete, and Local Database administrative Reset Password commit the user mutation and administrative audit evidence together. Any database error rolls back the session and does not report an operation as successful; lifecycle routes render a recoverable failure notification while password reset keeps validation feedback in its secure form. Existing last-active-local-Super-Admin serialization, soft-delete/restore-inactive, permission gates, and generation-bound session revocation remain authoritative. Forced-flush/commit failure and real PostgreSQL testing are UAT gates, not inferred from source checks.

## User Create/Edit database failure feedback

User Create/Edit services remain the sole transaction owner and atomically persist the user with administrative audit evidence. Unique username/email conflicts retain dedicated form errors; other `SQLAlchemyError` failures are rolled back by the service and translated by the route into sanitized retry guidance on the existing form, without leaking server diagnostics or fabricating a successful account change. CSRF, role delegation, local credential ownership and the User Edit committed-version check remain unchanged.

## User Directory inline detail composition

User Directory keeps its **inline expandable row** (not a new modal). Its committed User Detail renders within the existing `detail_ui.resource_sheet` and five compact `detail_ui.inventory_section` bands: Identity, Authentication, Authorization, Lifecycle, and Administrative Actions. Fact placement is **adaptive by domain**: Identity is 2×2 (User ID/Username followed by Display Name/Email), Authentication and Authorization use up to three columns for short facts, and Lifecycle uses up to four columns at desktop width. Email remains safely breakable beside Display Name; Last Authentication may span the available remaining authentication columns. Credential-ownership guidance and Effective Access explanations retain dedicated wrap-capable full-width rows. Unlike the former four-card 2×2 grid, each band follows its own content height without artificial equal-height whitespace. Provider identity, linked account, Local Database credential ownership, lifecycle timestamps, role/admission evidence and admin actions continue to use existing committed presentation data.

**Edit is owned by the User Directory row only**, avoiding duplicate Edit actions inside the expansion. Detail actions align to the right on desktop and wrap naturally on narrower screens; they remain gated by the same server-owned per-user RBAC/lifecycle decisions, with existing CSRF, HTMX lifecycle refresh and destructive confirmation unchanged. The shared `expandable.toggle_button` supports an **opt-in `compact=true`** variant for User Directory with `Details / Hide Details` wording and chevron, preserving all data/ARIA controls and leaving the established default presentation untouched for other registries. Mobile/light-dark and keyboard behavior require DevContainer human Visual QA before acceptance.

## User Directory canonical registry interaction

User Directory retains `#users-page-content` for mutation feedback, domain summary and out-of-band Hero/toast refresh. The standalone `#user-directory` surface owns only search, account state, identity source, role, Clear Filters, Rows and pagination via the approved `table_registry.filter_form`, `clear_filters_link`, and `footer` macros. These registry GETs return only the directory fragment, preserving the canonical latest-request-wins synchronization, loading indicator, query history, default five rows and 5/10/25/50 options. `per_page` is not duplicated in the Rows form. HTMX history restore and ordinary browser navigation return a full page; user lifecycle HTMX actions continue to refresh the full users-page-content and OOB Hero/toast. User detail expansion, action permission guards, CSRF and soft deletion remain unchanged.

### UAT-1(1) Access copy review — #2251

Shared Access summaries, role detail bands and User Management posture cards now use shorter presentation-only helper sentences to reduce avoidable desktop wrapping. Role/permission identity, inherited dependencies, role guard/permission constraints, source-scoped Activity Audit, verified Data Lifecycle archive and break-glass authority remain authoritative and unchanged. This human review supersedes older literal helper-copy expectations (including the formerly fixed inactive-role phrase) but does not supersede authorization or semantic contracts. Responsive/mobile and light/dark browser UAT remains NOT RUN until executed.

### UAT-1(1) count badge placement — #2252

Permission Registry, Role Coverage, and Administrative Source Evidence use the same shared `table_label.result_count` next to each table title, based on the current filtered result total. Tab navigation labels remain without counts. Filter actions, page size 5 and optional 10/25/50, HTMX and source permissions are unchanged; browser accessibility/visual review pending.

### UAT-1(1) lifecycle card alignment — #2253

The Add/Edit User `Lifecycle & Administrative Controls` section reuses the existing Super Admin card's Violet header geometry for Assigned Role, Active Account and eligible Super Admin, with concise descriptions that wrap naturally at phone/zoom widths. Actual role selection, account active state, Super Admin eligibility, unavailable branch, same-account restrictions, and last-active-Local-Super-Admin safeguards have not changed. Functional/browser UAT remains NOT RUN.



### UAT-1(2) Access Boundaries section hierarchy — #2257

Access Overview now places its **Access Boundaries** heading and supporting explanation above the existing read-only boundary grid, using the shared `section_intro` and `operational_section.shell_classes` primitives in the same outer section rhythm as Authorization Flow. The boundary titles/statuses, permission-scoped domain composition, responsive grid and zero-boundary omission are unchanged. Screenshot-based laptop/mobile/light-dark human acceptance remains pending.


### UAT-1(3) Identity Governance — #1335

Four Identity Governance descriptions are shortened for the Firefox Lenovo L13 sidebar-open layout. Provider ownership, external secrets and KAORI authorization remain authoritative. Only copy is changed; no truncation or forced nowrap. Mobile and zoom may wrap naturally. Browser acceptance is pending.


### UAT-1(4) Access modal header/footer — #2261

Access detail dialogs keep the existing `resource_detail_modal.host` chrome and their own body/width. User/Role destructive confirmations opt into a matching surface-card header with close control and contextual footer, preserving original body, dimensions, safe cancellation and protected confirmation actions. No default change applies to destructive confirmations elsewhere. Focus, keyboard, mobile/light-dark and destructive negative UAT are pending.

### UAT-1(4) Add User copy refinement — #2253

On the create-user page, remove the redundant Display Name default helper and Assigned Role post-login helper (without removing the field or conditional administrator-role restriction). Shorten password/identity-owner guidance, provider-admission steps and the three Administrative Boundary descriptions to reduce laptop side-rail wrapping while retaining Local Database-only break-glass and last-active-Super-Admin protections. Input values, validation, authorization and identity-provider workflow are unchanged; live Firefox/browser UAT remains pending.


### UAT-1(5) modal header reference — #2261

The newly supplied reference screenshot is **Permission Detail / `users.delete`** (title `Delete Users`, Canonical state, identity/dependency description and Access/permission/delegation badges), not the Delete User confirmation. Role Detail and Activity Detail retain their own authoritative data but now use the same header information order: icon, title with real status, description, metadata. Only Access destructive confirmations opt into matching header organization, using `Confirmation Required` and existing scope/action rather than mislabeling destructive operations as Canonical. The shared Permission Detail host footer defines the footer standard; the cropped screenshot itself does not display a footer. Body, modal dimensions, mutation buttons and permission controls remain unchanged. Executable and browser UAT, responsive Visual QA, focus restoration and human acceptance are pending.

### REVIEW(2) Access Overview User count text — #2251

The User Management posture caption in the read-only Access Overview uses
the same authoritative `build_user_access_summary()` counts and active
Local Database break-glass coverage. Only the human-facing text is shortened
to a correctly pluralized `accounts · active Local DB break-glass admin(s)`
statement, preserving all zero-active, no-admin and admission-warning
precedence branches. This is a Firefox L13 one-line **target**, not a claimed
browser PASS; actual responsive/zoom/light-dark and human UAT remains pending.
No persistence, aggregation or provider calls are added.

## REVIEW(4) — Role form text and Guide (#2307)

Firefox Lenovo L13 operator review shortens the Assignment Availability
caption while retaining an explicit deactivation/effective-access
consequence and the visible active/inactive status badge. The Access
Guardrails rail keeps four role policy boundaries as readable, natural
two-line desktop captions, including source-controlled dependencies,
effective delegation and Local Database-only Super Admin separation.
Static Role Slug and Display Name helper guidance is consolidated in the
canonical title-adjacent `info_tip` Guide in **Role Identity**. Labels,
input values, audit-sensitive errors, role lifecycle/CSRF, default-role
protection and backend authorization enforcement remain unchanged.
Desktop 1-/2-line targets are not guaranteed by a static copy budget;
actual Dev Container Firefox visual, accessibility and human acceptance
evidence remains PENDING. Official admission is HOLD.

## REVIEW(4) — Permission Matrix description rhythm (#2308)

The Roles permission-card description region reserves two ordinary lines of
vertical space using existing Tailwind `min-h-10` and `leading-5` rhythm.
Cards continue to show the complete authoritative `Permission.description`
without rewriting canonical RBAC or database metadata. Longer explanations
wrap fully at laptop, mobile, or zoom; shorter ones remain unchanged, with
no invented policy text or ellipsis. This is a *minimum two-line space*, not
a claim that every permission description comprises exactly two written
lines. Firefox Visual QA, source/registry integrity, and human acceptance
remain pending. Official admission remains HOLD.

## REVIEW(4) follow-up — descriptive content, not only two-line height (#2308)

The operator's Manage Integrations screenshot clarifies that the purpose is
**meaningfully descriptive copy for each of the 64 Permission Matrix
capabilities**, normally about two natural lines at Firefox Lenovo L13
width, not merely reserving `min-h-10` vertical space. Every permission's
source-owned `matrix_description` in the existing RBAC catalog describes
the specific allowed action and its target/scope. Role Editor reads this
copy from the committed catalog through `build_role_form_context()`, with
original persisted descriptions retained as fallback for unexpected
non-canonical/database-only records. Search also includes the richer copy.
The old `min-h-10` line-height rhythm remains, with natural wrapping and
no clipping. **Canonical RBAC descriptions, seeding, authorization, grants,
dependencies, Permission Catalog and database contents are unchanged.**
Real Firefox two-line appearance is a visual target rather than a source
PASS. Local focused pytest/Jinja, responsive/light-dark/zoom/browser
accessibility, negative RBAC and human acceptance remain pending. Official
staging admission, deployment and release are HOLD.

## Resource Scoped Grant Lifecycle (review implementation)

The #724 accepted architecture uses a dedicated Access-owned storage model
`app/models/scope_access.py` (#2723) and backend-only governed transition
service `app/access/scoped_grants.py` (#2724). It reuses canonical RBAC
and `stage_operational_activity` with `commit=False` so a draft, approval
or revocation **and** its mandatory audit event persist in one transaction
or both roll back. High-sensitivity grants require a different requestor
and approver, a current policy revision, an active human with qualified
Access admin permissions, active subject Role→Permission and exact approved
IntegrationInstance/Vault mount identity.

No UI/API/workers have been wired; do not call this service as a Secret access
decision, use it as a general RBAC bypass or treat schema arrival as grant
activation. Source-scoped decisions, IdP principals and migration cutover
remain in #2725/#2726. Run approved DevContainer schema upgrade via
the dedicated `db-bootstrap --upgrade-only` service, **not** by running
`flask db upgrade` as kaori_runtime.

## Exact scoped policy evaluator (HV #2725 — internal only)

`app/access/scope_policy.py` checks the latest persisted policy revision
from canonical Access state using the active KAORI `User.id` and
normalized role `secrets_pki.view`, exact IntegrationInstance/Vault source,
approved namespace and KV v2 mount. Draft/suspended/revoked/expired/unknown
policy versions deny; an instance-only grant never inherits to the mount.
The new `read_governed_scoped_secret_registry` is the **only candidate**
for future web/service adapters. It keeps the policy row locked through
the existing bounded committed Secret Registry read, writes mandatory
sanitized Activity Audit in that transaction, and returns rows only after
successful commit; failure rolls back and returns an uninformative denied page.

The legacy `read_scoped_secret_registry(decision=...)` is a lower-level
unpublished test/read-model helper and **must never be a route entrypoint**
because the caller can construct a synthetic decision. No HTTP, HTMX,
worker, Secret detail or grant-admin UI exposes either function now.
Future #2726 and security UAT must establish trusted session identity,
negative tests and request/job enforcement before publication.

## Shadow RBAC/scoped policy parity (#2726)

`app/access/scope_parity.py` provides an **internal**, read-only,
non-enforcing comparison of the existing effective `User.has_permission`
decision and the new exact Vault instance+mount source-policy admission.
Every result is a sanitized classification; grouped summaries contain
counts only (bounded to 200), never usernames, Secret paths, source
identifiers, Vault credentials or role membership. An unavailable scoped
decision is a **review finding**, not a permit and not a rollback to global
RBAC.

No current route, worker, report, API or permission has been changed to
enforce scope. Safe existing global aggregate pages retain their existing
RBAC contract, while new per-Secret Registry/Detail routes stay unpublished.
A real cutover requires an approved role/principal parity matrix, explicit
minimum grants, transactional audit tests, security/DevContainer UAT,
Full Admission and human acceptance. Rolling back an unpublished sensitive
route must not make it an unscoped read.

## Activity Audit register source hover info (#2885, 2026-10-23)

The approved title-level standard is `docs/design/components/INFO_TIP.md`
and `docs/design/components/TABLE_AND_LABEL.md`, reaffirmed in design
audit #2416. Before implementing header hover guidance, compare the
current standard *and at least one merged title-level consumer*; require
the existing `tests/contracts/design/test_info_tip_guide_rollout_contract.py`
to include this title-level consumer. Do not infer the correct variant
from the shared macro's default or a single local precedent.

Functional **Access → Activity Audit UAT is operator-approved**; the
follow-up enhances only the two register headers. Activity Register and
Administrative Source Evidence each use the existing title-level
`components/info_tip.html::render(..., variant='guide')` Violet Guide
directly next to the owning title, before the result-count badge.
An icon-only question-mark is reserved for genuinely field/row-level help. One tooltip describes Notification-backed hot
activity with immutable actor snapshots and separately owned Data
Lifecycle archive artifacts; the other describes source-permissioned hot
`AuditEvent` records from Automatic Jobs/Tenant Inventory Sync, actor FK
limitations, and Job Archive **bundle-level only** navigation.

The two sources and their counts remain independent; no storage union,
cross-source permission, archive record resolver, mutation, loading,
pagination, HTMX behavior or existing modal is changed. Shared Info Tip
owns keyboard/pointer/touch activation and viewport positioning.
Human hover/mobile/light-dark acceptance is pending separately from the
accepted overall Activity Audit functionality.

## Administrative AuditEvent Data Lifecycle boundary (#2889/#2890)

Access → Activity Audit contains two independent committed source views:
**Activity Register** reads `notifications` and uses
`operational_activity` retention; **Administrative Source Evidence**
selects allowed hot `audit_events` from Automatic Jobs/Tenant Inventory
Sync according to their source permissions. The new registered
`audit_event` Data Lifecycle domain is a separate, **paused, manual
archive-only** adapter for the underlying AuditEvent table (which contains
other producers too); it does not union the displays or grant additional
source access. It archives minimal redacted summaries and preserves all
hot records. Hot cleanup, automated schedules, archive-object purge,
individual-record lookup and bundle download are blocked pending
source-specific retention/privacy/legal-hold and RBAC authority (#2891).
Until that admission, the domain, aggregate counts, Preview and archive history
are **Local Database Super Admin-only**, and mutations enforce the same
boundary independent of UI; even Super Admin cannot download these bundles.
Verified compaction remains a separate workstream (#2892). Archive History is artifact-level,
not a verified lookup for the selected administrative event or a missing
JobExecution. Do not infer immutable actor identity from AuditEvent FK.
