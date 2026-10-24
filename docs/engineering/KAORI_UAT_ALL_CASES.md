# KAORI — Complete Acceptance Case Specifications (106 scenarios)

**Authority:** #1738 scenario catalog / #1725 QA contract. Test procedures are proposed acceptance specifications, not machine execution results. Every written case still requires exact-candidate executable test-node mapping, runtime evidence and separate human sign-off.

**Maturity:** Original 14 first-wave procedures retained; the other 92 are expanded and require capability-owner review. No machine scenario is counted PASS. Each newly authored Gherkin ID remains NOT RUN for scenario-attributed automation evidence. The operator explicitly Human Accepted the bounded Kubernetes Admin Batch 01–06 workflow under #2605, while unexercised security and visual coverage remains a separate QA backlog.

**Runtime:** Existing pytest/Playwright runners only; real-provider/destructive operations require approved sandbox. Screenshots, traces, JUnit, committed data and audit evidence must be candidate/run-bound.

## Authentication & Sessions

**Owner:** app/access/authentication/.  
**Candidate pytest/Playwright suites:** tests/access/authentication/; tests/security/access/; tests/ui/.  

### UAT-AUT-001 — Valid active user logs in

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Local test user, session fixtures and configured auth method; never expose real credentials; active user with known permission and a protected capability.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Valid active user logs in.
2. Perform the scenario action using an approved browser or domain test client: Valid active user logs in.
3. open that protected capability after submitting correct credentials, then inspect session and Activity.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-001.

**Expected results:**
- Authenticated session, authorized navigation and correct audit/feedback are produced.
- session principal and permitted navigation agree; one authentication success is attributable.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/access/authentication/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-AUT-002 — Invalid login never admits a session

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** A test account exists; a known invalid password can be supplied. Use only disposable credentials.

**Steps:**
1. Open the canonical sign-in page with Playwright.
2. Fill username and invalid password; click submit.
3. Attempt to navigate directly to a protected capability URL and inspect server session state.

**Expected results:**
- No authenticated session or protected content is granted.
- The form displays an actionable, non-enumerating authentication failure.
- No token, password or private identity data appears in screenshot/trace/audit.

**Required evidence:** Browser trace, sanitized response, session/access assertion and server-side auth result.

**Isolation / cleanup:** Never publish credential input or auth cookie in CI traces.

**Automation mapping:** Not validated. Inspect assertions under tests/access/authentication/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-AUT-003 — Expired/revoked session submits a protected request

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Local test user, session fixtures and configured auth method; never expose real credentials; an admitted session whose version can be revoked or expired.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Expired/revoked session submits a protected request.
2. Perform the scenario action using an approved domain/service test client: Expired/revoked session submits a protected request.
3. reuse the earlier cookie for a protected direct POST after revocation.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-003.

**Expected results:**
- Server rejects request regardless of previously rendered UI.
- server independently denies access and does not create a new session or commit a mutation.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/access/authentication/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-AUT-004 — CSRF token is missing/invalid on a protected mutation

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Local test user, session fixtures and configured auth method; never expose real credentials; disposable protected mutation and known valid CSRF form.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: CSRF token is missing/invalid on a protected mutation.
2. Perform the scenario action using an approved browser or domain test client: CSRF token is missing/invalid on a protected mutation.
3. retry once with no token and once with a mismatched token.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-004.

**Expected results:**
- Mutation rejected with no committed/provider side effects.
- neither attempt changes persisted or provider state or produces a success Activity event.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/access/authentication/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-AUT-005 — User signs out and uses Back or bookmarked authenticated URL

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Local test user, session fixtures and configured auth method; never expose real credentials; valid authenticated session and bookmarked protected URL.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: User signs out and uses Back or bookmarked authenticated URL.
2. Perform the scenario action using an approved browser or domain test client: User signs out and uses Back or bookmarked authenticated URL.
3. log out, press Back, and request bookmarked URL again.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-005.

**Expected results:**
- Session ended, protected content cannot be recovered without login.
- fresh protected response is denied and browser history does not restore authorization.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/access/authentication/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

## Access — Users, Roles, Permissions & Identity Providers

**Owner:** app/access/README.md; app/access/rbac/; app/access/identity_providers/.  
**Candidate pytest/Playwright suites:** tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.  

### UAT-IAM-001 — Permitted admin creates/updates user and role assignment

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; disposable target user, admin and allowed role.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Permitted admin creates/updates user and role assignment.
2. Perform the scenario action using an approved browser or domain test client: Permitted admin creates/updates user and role assignment.
3. save a role assignment then reload directory and effective permission as new request.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-001.

**Expected results:**
- Persisted identity/role state, correct directory UI, safe Activity evidence.
- persisted memberships and actor/target audit match approved input.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-IAM-002 — Restricted user cannot mutate Users or Roles through direct requests

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Two local test principals with known disjoint role permissions and disposable User/Role fixtures.

**Steps:**
1. Sign in as a restricted user; confirm role mutation action is not falsely advertised.
2. Invoke a direct protected mutation URL/API as that user, including valid CSRF material when relevant.
3. Read User/Role records and Activity to inspect post-request state.

**Expected results:**
- Server rejects unauthorized access regardless of UI visibility.
- No role membership, privilege or administrative object changes.
- Error response/UI is safe and does not leak sensitive role details.

**Required evidence:** Playwright response and screenshot, denied permission assertion, before/after persisted state.

**Isolation / cleanup:** Do not test escalation on a production administrative identity.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-IAM-003 — Protected role or forbidden permission escalation is submitted

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; protected role and forbidden permission escalation fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Protected role or forbidden permission escalation is submitted.
2. Perform the scenario action using an approved domain/service test client: Protected role or forbidden permission escalation is submitted.
3. post escalation directly, then reload effective roles under new session.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-003.

**Expected results:**
- Canonical RBAC guard rejects; no effective privilege expansion.
- guard denies and grants do not expand even if navigation is hidden.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-IAM-004 — Admin filters User Directory/Permission Catalog and clears filters

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; directory with 12 users and distinct permission catalog entries.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Admin filters User Directory/Permission Catalog and clears filters.
2. Perform the scenario action using an approved browser or domain test client: Admin filters User Directory/Permission Catalog and clears filters.
3. filter, switch Rows 5 to 10 and clear filters after HTMX refresh.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-004.

**Expected results:**
- Canonical default five rows, page one reset, selected row count preserved.
- page resets to one and chosen Rows remains ten.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-IAM-005 — Identity Provider is disabled, invalid or unreachable during auth

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; disabled or unreachable disposable identity provider.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Identity Provider is disabled, invalid or unreachable during auth.
2. Perform the scenario action using an approved browser or domain test client: Identity Provider is disabled, invalid or unreachable during auth.
3. attempt provider login then direct protected URL and inspect fallback.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-005.

**Expected results:**
- No fallback that admits an unauthorized identity; error state identifies dependency.
- no alternative authentication path admits the failed external principal.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-IAM-006 — Role/user modal or validation form receives missing and malformed fields

**Type:** Negative · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; empty and malformed fields on a disposable role/user modal.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Role/user modal or validation form receives missing and malformed fields.
2. Perform the scenario action using an approved browser or domain test client: Role/user modal or validation form receives missing and malformed fields.
3. submit twice and inspect validation focus and persisted entity count.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-006.

**Expected results:**
- Actionable inline error; no partial entity creation; focus retained.
- accessible errors remain visible; no partial entity is created.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/.; do not infer coverage from filename.

### UAT-IAM-007 — Viewer cannot open Access Overview through a direct read request

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Authenticated default Viewer test principal lacking users.view, users.manage, identity_providers.view, roles.view and activity_audit.view; isolated environment and captured effective permissions.

**Steps:**
1. Sign in as the Viewer and verify absence of Access workspace permission in the role fixture.
2. Request GET /access/ directly, bypassing Welcome and sidebar navigation.
3. Assert the actual document response status and inspect the returned Access Denied HTML.
4. Confirm protected Access Overview content is absent and no administrative state was modified.

**Expected results:**
- HTTP 403 Forbidden is returned by the server, not a client-side hidden-card fallback.
- Accessible Access Denied guidance shows Viewer, blocked access, an administrator contact path and safe Welcome navigation.
- No protected user/role/identity provider data or unauthorized administrative side effect is disclosed.

**Required evidence:** Exact request/response status 403, authenticated role permission read-back, browser screenshot/trace, safe HTML assertions and negative authorization test JUnit; 2026-10-24 operator Network screenshot recorded separately on #746.

**Isolation / cleanup:** Use a disposable Viewer principal and isolated authorization fixture; do not perform role/user mutations or expose user secrets.

**Automation mapping:** Partial: app/access/overview/routes.py @any_permission_required and app/access/rbac/decorators.py abort(403) are source-reviewed; this specific Viewer read-only document request needs exact-candidate automated HTTP/HTML regression mapping, distinct from UAT-IAM-002 mutation denial.

## Kubernetes — Cluster Registration & Provider Readiness

**Owner:** app/kubernetes/cluster/; app/integrations/orchestration/.  
**Candidate pytest/Playwright suites:** tests/contracts/kubernetes/; tests/kubernetes/; tests/integrations/.  

### UAT-KCL-001 — Permitted operator registers a valid cluster and validates connection

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; disposable authorized Kubernetes endpoint.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Permitted operator registers a valid cluster and validates connection.
2. Perform the scenario action using an approved browser or domain test client: Permitted operator registers a valid cluster and validates connection.
3. register exact endpoint, validate, then reread cluster configuration.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-001.

**Expected results:**
- Correct cluster identity/readiness, committed configuration and audit evidence.
- committed readiness and provider cluster identity are the same.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/kubernetes/; tests/kubernetes/; tests/integrations/.; do not infer coverage from filename.

### UAT-KCL-002 — Cluster credentials/endpoint/TLS trust are invalid

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; invalid Kubernetes CA, credentials or endpoint fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Cluster credentials/endpoint/TLS trust are invalid.
2. Perform the scenario action using an approved browser or domain test client: Cluster credentials/endpoint/TLS trust are invalid.
3. validate each invalid setting and reload cluster detail.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-002.

**Expected results:**
- Clear validation failure; no false Connected/Ready state or leaked credential.
- no false Connected badge and no credential disclosed in response.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/kubernetes/; tests/kubernetes/; tests/integrations/.; do not infer coverage from filename.

### UAT-KCL-003 — Provider is unavailable after committed cluster inventory exists

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; previous committed cluster snapshot and newly unreachable API.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Provider is unavailable after committed cluster inventory exists.
2. Perform the scenario action using an approved domain/service test client: Provider is unavailable after committed cluster inventory exists.
3. open inventory then attempt provider-dependent write during outage.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-003.

**Expected results:**
- Read-only committed state remains truthful; live writes fail closed.
- snapshot remains provenance-labeled and the write is rejected.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/kubernetes/; tests/kubernetes/; tests/integrations/.; do not infer coverage from filename.

### UAT-KCL-004 — Restricted user submits cluster configuration mutation

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; restricted identity and committed Cluster baseline.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Restricted user submits cluster configuration mutation.
2. Perform the scenario action using an approved browser or domain test client: Restricted user submits cluster configuration mutation.
3. issue direct cluster-mutation POST then reload connection identity.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-004.

**Expected results:**
- Authorization denial and no external or committed mutation.
- RBAC denial preserves endpoint and credential references.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/kubernetes/; tests/kubernetes/; tests/integrations/.; do not infer coverage from filename.

## Kubernetes — Dashboard, Inventory & Topology

**Owner:** app/kubernetes/dashboard/; app/kubernetes/inventory/.  
**Candidate pytest/Playwright suites:** tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/.  

### UAT-INV-001 — Operator opens Cluster/Dashboard then Inventory lists and details

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; committed objects with distinct UIDs on two clusters.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator opens Cluster/Dashboard then Inventory lists and details.
2. Perform the scenario action using an approved browser or domain test client: Operator opens Cluster/Dashboard then Inventory lists and details.
3. open object detail on cluster A then repeat on cluster B.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-001.

**Expected results:**
- Correct selected-cluster scope, navigation, row/detail identity and shared table UI.
- object, row, breadcrumb and source IDs never cross clusters.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-INV-002 — Inventory evidence is stale, missing or partially collected

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; stale, partially collected and absent inventory snapshots.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Inventory evidence is stale, missing or partially collected.
2. Perform the scenario action using an approved browser or domain test client: Inventory evidence is stale, missing or partially collected.
3. open each state and inspect freshness and missing-object displays.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-002.

**Expected results:**
- UI explicitly displays stale/partial/unknown, not fabricated Healthy/zero.
- unknown is not fabricated zero/healthy and partial evidence is labeled.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-INV-003 — Same-name object is recreated with a different provider UID

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; same object name recreated with a new Kubernetes UID.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Same-name object is recreated with a different provider UID.
2. Perform the scenario action using an approved domain/service test client: Same-name object is recreated with a different provider UID.
3. compare previous and new generation in detail/correlation.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-003.

**Expected results:**
- Old/new identities are not conflated; lineage and correlation remain correct.
- lineage differentiates both UIDs without reusing old identity.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-INV-004 — Filter/sort/page Inventory records including zero-result state

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; at least 11 inventory rows plus unmatched search.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Filter/sort/page Inventory records including zero-result state.
2. Perform the scenario action using an approved browser or domain test client: Filter/sort/page Inventory records including zero-result state.
3. sort/filter, change page and Rows then clear filters.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-004.

**Expected results:**
- Filters persist across HTMX navigation; pagination and No Results follow shared standard.
- HTMX preserves selection and no-result/page-reset semantics.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-INV-005 — Topology relationship source is absent or inconsistent

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; topology missing one relationship and similarly named foreign-cluster node.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Topology relationship source is absent or inconsistent.
2. Perform the scenario action using an approved browser or domain test client: Topology relationship source is absent or inconsistent.
3. remove relationship source then inspect graph and detail.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-005.

**Expected results:**
- No invented dependency edges or misleading cross-cluster relationship.
- no inferred/cross-cluster edge appears without authoritative evidence.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

## Kubernetes — Analytics & Forecast

**Owner:** app/kubernetes/analytics/; app/analytics/.  
**Candidate pytest/Playwright suites:** tests/kubernetes/analytics/; tests/contracts/analytics/; tests/ui/.  

### UAT-KAN-001 — Operator selects cluster/time range and opens utilization/capacity/forecast

**Type:** Positive · **Layer:** Both · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; two cluster metric snapshots and two time windows.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator selects cluster/time range and opens utilization/capacity/forecast.
2. Perform the scenario action using an approved browser or domain test client: Operator selects cluster/time range and opens utilization/capacity/forecast.
3. switch scope/window then inspect chart series, units and timestamps.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-001.

**Expected results:**
- Charts and summaries retain chosen scope, units, time window and source freshness.
- aggregates and forecasts retain exact source and selected scope.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/analytics/; tests/contracts/analytics/; tests/ui/.; do not infer coverage from filename.

### UAT-KAN-002 — Metrics source becomes unavailable or returns no data

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; missing, stale and disconnected metrics provider fixtures.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Metrics source becomes unavailable or returns no data.
2. Perform the scenario action using an approved browser or domain test client: Metrics source becomes unavailable or returns no data.
3. open chart/KPI for each failure and inspect tooltip readiness.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-002.

**Expected results:**
- Never display zero as measured utilization or unknown as Normal.
- unknown utilization is never plotted as observed zero/normal.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/analytics/; tests/contracts/analytics/; tests/ui/.; do not infer coverage from filename.

### UAT-KAN-003 — Invalid/out-of-scope metrics binding or scope is submitted

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; wrong-cluster or invalid metric source binding.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Invalid/out-of-scope metrics binding or scope is submitted.
2. Perform the scenario action using an approved domain/service test client: Invalid/out-of-scope metrics binding or scope is submitted.
3. submit invalid analytics scope then inspect persisted output.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-003.

**Expected results:**
- No cross-cluster fallback or fabricated demand/capacity forecast.
- cross-cluster substitution and fabricated forecast are rejected.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/analytics/; tests/contracts/analytics/; tests/ui/.; do not infer coverage from filename.

### UAT-KAN-004 — Charts, selectors and tables render under light/dark and narrow viewports

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; deterministic charts in light/dark with six viewport sizes.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Charts, selectors and tables render under light/dark and narrow viewports.
2. Perform the scenario action using an approved browser or domain test client: Charts, selectors and tables render under light/dark and narrow viewports.
3. interact with chart legend, tooltip and selector in each viewport.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-004.

**Expected results:**
- Labels/legends visible, no horizontal document overflow or clipped actions.
- no clipped labels, illegible contrast or document overflow.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/analytics/; tests/contracts/analytics/; tests/ui/.; do not infer coverage from filename.

## Kubernetes — Governance & TLS

**Owner:** app/kubernetes/governance/; app/kubernetes/operations/.  
**Candidate pytest/Playwright suites:** tests/kubernetes/governance/; tests/kubernetes/operations/; tests/security/kubernetes/.  

### UAT-GOV-001 — Operator reviews TLS certificate inventory and governance finding

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; known TLS cert SAN, issuer, expiration and committed source.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator reviews TLS certificate inventory and governance finding.
2. Perform the scenario action using an approved browser or domain test client: Operator reviews TLS certificate inventory and governance finding.
3. open Governance certificate finding and authoritative detail.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-001.

**Expected results:**
- Certificate identity, expiry/source and readiness reflect authoritative evidence.
- certificate fields and readiness match committed certificate identity.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/governance/; tests/kubernetes/operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-GOV-002 — TLS rotation preflight fails (identity/permission/impact)

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; disposable TLS Secret and deliberately failed preflight.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: TLS rotation preflight fails (identity/permission/impact).
2. Perform the scenario action using an approved browser or domain test client: TLS rotation preflight fails (identity/permission/impact).
3. record fingerprint/UID, attempt rotation and reobserve provider.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-002.

**Expected results:**
- Change is blocked; original Secret/cert remains unchanged.
- no cert replacement or success claim after failure.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/governance/; tests/kubernetes/operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-GOV-003 — Capacity/quota or policy evidence is expired or conflicting

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; expired capacity policy snapshot and positive quota request.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Capacity/quota or policy evidence is expired or conflicting.
2. Perform the scenario action using an approved domain/service test client: Capacity/quota or policy evidence is expired or conflicting.
3. submit guarded quota change and reread decision and provider.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-003.

**Expected results:**
- Mutation admission fails closed; no optimistic capacity claims.
- fail-closed admission preserves quota and avoids optimistic capacity.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/governance/; tests/kubernetes/operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-GOV-004 — Operator moves from governance finding to source evidence

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; finding with linked evidence and another with missing source.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator moves from governance finding to source evidence.
2. Perform the scenario action using an approved browser or domain test client: Operator moves from governance finding to source evidence.
3. follow both finding links and inspect accessible blocked state.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-004.

**Expected results:**
- Scoped navigation, accessible details and consistent blocked/error states.
- valid link remains scoped and missing source never jumps to another asset.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/governance/; tests/kubernetes/operations/; tests/security/kubernetes/.; do not infer coverage from filename.

## Kubernetes — Tenant Management

**Owner:** app/kubernetes/tenant/README.md; #125.  
**Candidate pytest/Playwright suites:** tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.  

### UAT-TEN-001 — Native Namespace adoption preserves provider authority

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Approved disposable Native Namespace not owned by KAORI, baseline UID/resourceVersion, test operator with adoption permission; no Capsule ownership.

**Steps:**
1. Capture Kubernetes Namespace UID/resourceVersion, labels/owner references and applicable quota before test.
2. Navigate to Tenant Discovery/Adoption and select the exact Namespace.
3. Review Preflight and explicitly confirm the allowed adoption.
4. Inspect KAORI Tenant/Namespace committed record, generation and Activity; read back provider Namespace by exact UID.

**Expected results:**
- Exactly one adopted generation under correct cluster/provider/tenant scope.
- Committed evidence identifies the verified provider object; no duplicate governance owner.
- Only explicitly admitted provider writes occur; audit/mutation provenance is truthful.

**Required evidence:** Pre/post provider identity and object diff, UI screenshot/trace, committed Tenant/Namespace fields and Audit correlation.

**Isolation / cleanup:** Disposable Native Namespace only, read-back required and cleanup/recovery governed.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-002 — Stale Native Namespace preflight must fail closed

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Approved disposable Native Namespace; controlled test fixture may change its resourceVersion between valid Preflight and submit.

**Steps:**
1. Record baseline provider UID, resourceVersion and KAORI adopted records.
2. Complete Discovery and Preflight through browser.
3. Change Namespace resourceVersion through an approved isolated fixture.
4. Submit the original stale form and inspect UI response, KAORI database and provider read-back.

**Expected results:**
- No successful adoption; actionable error rather than success toast.
- No new adopted Tenant/Namespace generation and no unauthorized provider mutation.
- Audit does not falsely claim successful adoption; failed attempt can be correlated.

**Required evidence:** Version before/after, browser trace, response, DB diff, provider diff and Audit.

**Isolation / cleanup:** Use only approved test Namespace; do not create a conflict on real operational workloads.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-003 — Create Tenant/Namespace from approved Resource Profile within budget

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; enabled versioned profile and disposable Native Tenant within fresh budget.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Create Tenant/Namespace from approved Resource Profile within budget.
2. Perform the scenario action using an approved browser or domain test client: Create Tenant/Namespace from approved Resource Profile within budget.
3. submit Namespace provisioning then reread committed version and quota.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-003.

**Expected results:**
- Committed pinned profile version, allocation and provider read-back match.
- pinned profile and actual ResourceQuota/LimitRange match.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-004 — Capacity budget rejection prevents allocation mutation

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** A disposable Tenant allocation/provisioning fixture with committed capacity evidence and a proposed change exceeding available governed headroom.

**Steps:**
1. Open Namespace Provisioning/Allocation Change as allowed operator.
2. Enter an allocation exceeding the accepted cluster budget.
3. Inspect preview/shortfall/readiness, then attempt submit via UI or direct request.
4. Compare committed allocation version and provider ResourceQuota/LimitRange before and after.

**Expected results:**
- Preview shows truthful shortfall and blocks mutation.
- Server independently rejects an invalid/out-of-budget submit.
- Pinned allocation and provider quota/limits remain unchanged with no success audit.

**Required evidence:** Form/preview screenshot, validation response, capacity source fingerprint, committed version and provider read-back.

**Isolation / cleanup:** Never use a production allocation for boundary-failure testing.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-005 — Restricted or self-approving actor attempts credential/Access Grant escalation

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; restricted tenant principal and independent approver roles.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Restricted or self-approving actor attempts credential/Access Grant escalation.
2. Perform the scenario action using an approved browser or domain test client: Restricted or self-approving actor attempts credential/Access Grant escalation.
3. attempt credential/grant action and self-approval by direct request.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-005.

**Expected results:**
- Server denies or requires independent approval; secrets are not exposed.
- RBAC/maker-checker prevents unauthorized grant or secret exposure.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-006 — Provider patch succeeds but KAORI commit/read-back fails

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; sandbox Namespace with injected provider-patch then commit failure.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Provider patch succeeds but KAORI commit/read-back fails.
2. Perform the scenario action using an approved browser or domain test client: Provider patch succeeds but KAORI commit/read-back fails.
3. capture UID/quota, fail persistence and reread provider residue.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-006.

**Expected results:**
- No false complete state; recovery evidence identifies possible provider residue.
- failure/recovery evidence remains explicit and no Ready state is invented.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-007 — Resource Profile/Create/Allocation modal is opened and completed

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; disposable profile create/edit and Namespace allocation form.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Resource Profile/Create/Allocation modal is opened and completed.
2. Perform the scenario action using an approved browser or domain test client: Resource Profile/Create/Allocation modal is opened and completed.
3. open controls, submit malformed then valid input, reread pinned version.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-007.

**Expected results:**
- Shared modal/input/validation, labels, toast and frozen allocation version rendered correctly.
- modal focus/toast/validation and frozen profile version are consistent.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

### UAT-TEN-008 — Tenant released/re-adopted identity is reused or foreign Capsule owner appears

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; recreated Namespace UID or foreign Capsule owner fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Tenant released/re-adopted identity is reused or foreign Capsule owner appears.
2. Perform the scenario action using an approved browser or domain test client: Tenant released/re-adopted identity is reused or foreign Capsule owner appears.
3. attempt to adopt stale owner/generation then reread both identities.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-008.

**Expected results:**
- Fail closed against wrong generation/foreign owner; never silently take over.
- no takeover or historical generation rebinding occurs.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/.; do not infer coverage from filename.

## Kubernetes — ConfigMaps, Secrets & Resource Operations

**Owner:** app/kubernetes/operations/; app/platform_operations/kubernetes/.  
**Candidate pytest/Playwright suites:** tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/.  

### UAT-KOP-001 — Permitted operator creates/edits ConfigMap in sandbox

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; disposable ConfigMap in approved sandbox Namespace.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Permitted operator creates/edits ConfigMap in sandbox.
2. Perform the scenario action using an approved browser or domain test client: Permitted operator creates/edits ConfigMap in sandbox.
3. create/edit keys then read exact provider UID/resourceVersion.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-001.

**Expected results:**
- Provider read-back matches intended data; KAORI job/activity evidence accurate.
- provider content and job/Activity reflect the admitted mutation.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-KOP-002 — ConfigMap submit/delete uses stale identity, missing rights or conflict

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; stale ConfigMap version or restricted delete actor.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: ConfigMap submit/delete uses stale identity, missing rights or conflict.
2. Perform the scenario action using an approved browser or domain test client: ConfigMap submit/delete uses stale identity, missing rights or conflict.
3. submit edit/delete against stale UID then reobserve provider.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-002.

**Expected results:**
- No unintended overwrite/delete; operator gets actionable feedback.
- no overwrite/delete and actionable failure feedback.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-KOP-003 — Secret operation form loads and validates bounded metadata

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; safe Secret metadata fixture without real secret values.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Secret operation form loads and validates bounded metadata.
2. Perform the scenario action using an approved browser or domain test client: Secret operation form loads and validates bounded metadata.
3. open form and submit invalid metadata on mobile.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-003.

**Expected results:**
- Form labels, modal, loading, focus, feedback and layout follow shared standards.
- accessible error, focus and modal do not leak secret contents.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-KOP-004 — Secret reveal rejects user without approved policy

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Synthetic Secret in disposable namespace; test user lacks reveal policy/approval. Do not use real secret values.

**Steps:**
1. Visit permitted Kubernetes Administration/Secret Reveal surfaces as restricted user.
2. Attempt to open a protected reveal flow; also invoke direct reveal request where safe.
3. Inspect response, Activity, trace/log redaction and Secret state.

**Expected results:**
- Reveal is denied before any one-time disclosure occurs.
- Secret value never appears in browser DOM, response, screenshot, trace or logs.
- No false approved/revealed audit is recorded.

**Required evidence:** Denied HTTP/permission assertion, sanitized browser trace, audit state and negative secret-leak assertions.

**Isolation / cleanup:** Only non-sensitive known fixture Secret; redact every captured artifact.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-KOP-005 — TLS Secret rotation encounters wrong target or partial provider failure

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; disposable TLS Secret with wrong target or injected partial failure.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: TLS Secret rotation encounters wrong target or partial provider failure.
2. Perform the scenario action using an approved domain/service test client: TLS Secret rotation encounters wrong target or partial provider failure.
3. attempt controlled rotation then compare fingerprint/version.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-005.

**Expected results:**
- No false rotation success; pre/post identity and recovery evidence preserved.
- no false rotation success; recovery and original identity remain visible.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/.; do not infer coverage from filename.

## Object Storage — Inventory & Analytics

**Owner:** app/storage/object_storage/; app/integrations/storage/object_storage/.  
**Candidate pytest/Playwright suites:** tests/storage/object_storage/; tests/contracts/storage/; tests/integrations/.  

### UAT-OST-001 — Operator views registered Object Storage systems and bucket inventory

**Type:** Positive · **Layer:** Both · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; two Object Storage systems with distinct committed bucket inventories.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator views registered Object Storage systems and bucket inventory.
2. Perform the scenario action using an approved browser or domain test client: Operator views registered Object Storage systems and bucket inventory.
3. open bucket detail for selected system and inspect source age.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-001.

**Expected results:**
- Correct system identity, bucket scope, committed metrics and details.
- metrics and bucket rows do not mix systems.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/storage/object_storage/; tests/contracts/storage/; tests/integrations/.; do not infer coverage from filename.

### UAT-OST-002 — Object Storage provider is unreachable, disabled or returns partial results

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; previous storage snapshot plus provider outage/partial listing.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Object Storage provider is unreachable, disabled or returns partial results.
2. Perform the scenario action using an approved browser or domain test client: Object Storage provider is unreachable, disabled or returns partial results.
3. reload inventory and readiness under disconnected source.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-002.

**Expected results:**
- Truthful unknown/stale/degraded presentation; no fabricated empty bucket list.
- UI is stale/partial/unknown instead of empty/healthy.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/storage/object_storage/; tests/contracts/storage/; tests/integrations/.; do not infer coverage from filename.

### UAT-OST-003 — Bucket registry search/filter/pagination and details interaction

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; bucket registry exceeding five rows with unmatched search.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Bucket registry search/filter/pagination and details interaction.
2. Perform the scenario action using an approved browser or domain test client: Bucket registry search/filter/pagination and details interaction.
3. filter, change Rows, clear and open bucket detail on mobile.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-003.

**Expected results:**
- Five-row default, stable filters, accessible detail/modal and clear feedback.
- table defaults five and remains responsive/accessible.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/storage/object_storage/; tests/contracts/storage/; tests/integrations/.; do not infer coverage from filename.

### UAT-OST-004 — Forecast/usage receives mismatched source or missing data

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; wrong system binding or missing usage evidence.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Forecast/usage receives mismatched source or missing data.
2. Perform the scenario action using an approved domain/service test client: Forecast/usage receives mismatched source or missing data.
3. request forecast under invalid source then inspect normalized output.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-004.

**Expected results:**
- No cross-system substitution, bogus zero capacity or unsupported trend claim.
- no cross-system substitution or bogus zero/trend.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/storage/object_storage/; tests/contracts/storage/; tests/integrations/.; do not infer coverage from filename.

## Artifact Registry — Inventory, Security, Runtime & Governance

**Owner:** app/artifact_registry/; #558.  
**Candidate pytest/Playwright suites:** tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/.  

### UAT-REG-001 — Operator inspects registry/artifact inventory and synchronized evidence

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; committed registry project/artifact/tag/digest generation.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator inspects registry/artifact inventory and synchronized evidence.
2. Perform the scenario action using an approved browser or domain test client: Operator inspects registry/artifact inventory and synchronized evidence.
3. filter registry/project, open artifact digest detail.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-001.

**Expected results:**
- Correct registry/project/artifact/version identity, freshness and pagination.
- identity and freshness match authoritative synchronized evidence.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/.; do not infer coverage from filename.

### UAT-REG-002 — Security vulnerability scan is absent, failed or partial

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; missing, failed and partial vulnerability scan fixtures.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Security vulnerability scan is absent, failed or partial.
2. Perform the scenario action using an approved browser or domain test client: Security vulnerability scan is absent, failed or partial.
3. open security posture and scan detail for each state.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-002.

**Expected results:**
- Unknown/partial posture not labeled Secure/Healthy.
- never label partial or unavailable scan Secure/Healthy.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/.; do not infer coverage from filename.

### UAT-REG-003 — Stale artifact-to-runtime identity cannot claim verified binding

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Two distinct registry/runtime identities or stale runtime snapshot fixture; no provider writes required.

**Steps:**
1. Record artifact registry identity and currently committed runtime binding evidence.
2. Make target cluster/runtime evidence stale, missing or identity-mismatched in fixture.
3. Open Runtime Usage/Topology details and inspect binding status.
4. Check underlying normalized correlation status against source fingerprint.

**Expected results:**
- UI labels missing/unverified/stale binding truthfully, not verified/Ready.
- No false artifact-to-runtime link or cross-cluster association is committed.
- UI remains navigable and usable in error/unknown state at supported viewports.

**Required evidence:** Normalized binding assertion, source fingerprint, UI detail screenshot, trace and empty/degraded state.

**Isolation / cleanup:** Read-only fixture; no registry image or cluster resource mutation.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/.; do not infer coverage from filename.

### UAT-REG-004 — User opens Runtime Usage topology/detail and applies scoped filters

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; runtime digest binding and two Kubernetes cluster snapshots.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: User opens Runtime Usage topology/detail and applies scoped filters.
2. Perform the scenario action using an approved browser or domain test client: User opens Runtime Usage topology/detail and applies scoped filters.
3. filter Runtime Usage and inspect topology identity/modal.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-004.

**Expected results:**
- Links/tabs/modal and filter states work with canonical responsive layout.
- links preserve registry digest and workload UID/cluster.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/.; do not infer coverage from filename.

### UAT-REG-005 — Registry provider disabled or sync failed after earlier success

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; historically Ready registry whose provider is now disabled/failed.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Registry provider disabled or sync failed after earlier success.
2. Perform the scenario action using an approved domain/service test client: Registry provider disabled or sync failed after earlier success.
3. reload readiness and affected consumer after provider state change.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-005.

**Expected results:**
- Latest committed source state truthfully supersedes old Ready evidence.
- historical Ready does not override current failed source.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/.; do not infer coverage from filename.

## Integrations — Registry, Provider Configuration & Runtime

**Owner:** app/integrations/README.md.  
**Candidate pytest/Playwright suites:** tests/integrations/; tests/contracts/integrations/; tests/ui/.  

### UAT-ING-001 — Operator registers an allowed provider instance and validates it

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; allowed capability, provider and disposable instance endpoint.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator registers an allowed provider instance and validates it.
2. Perform the scenario action using an approved browser or domain test client: Operator registers an allowed provider instance and validates it.
3. register instance then validate and reopen its detail.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-001.

**Expected results:**
- Capability-first domain/instance identity, sanitized connection readiness and audit.
- capability-first identity and sanitized readiness match provider.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-ING-002 — Invalid provider credentials/TLS do not produce Ready state

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Isolated Metrics Source, Alertmanager or Object Storage provider test instance with deliberately invalid validation inputs.

**Steps:**
1. Open the existing capability-first Integrations instance/configuration form.
2. Fill a non-secret invalid endpoint/certificate or disposable invalid credentials.
3. Trigger the owning provider validation and inspect operational UI feedback.
4. Inspect committed readiness/evidence and bound consuming views.

**Expected results:**
- Provider validation is rejected or degraded, never marked Ready.
- No fallback to another instance or cross-scope/source substitution.
- No sensitive validation payload in UI/audit/traces.

**Required evidence:** UI modal/validation trace, provider result, committed instance state, consumer posture and safe audit.

**Isolation / cleanup:** Use deliberate invalid sandbox configuration; preserve existing live integration instance configuration.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-ING-003 — Disabled or stale provider still has previously committed metrics

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; disabled provider with old successful committed metrics.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Disabled or stale provider still has previously committed metrics.
2. Perform the scenario action using an approved domain/service test client: Disabled or stale provider still has previously committed metrics.
3. inspect current consumer readiness after provider disable.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-003.

**Expected results:**
- Consumers cannot represent it as active/Ready or silently substitute data.
- old metrics remain historical; no active source substitution.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-ING-004 — Navigate Integrations Overview → capability → instance detail and actions

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; two instance statuses under one capability.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Navigate Integrations Overview → capability → instance detail and actions.
2. Perform the scenario action using an approved browser or domain test client: Navigate Integrations Overview → capability → instance detail and actions.
3. navigate Overview/capability/instance and trigger validate/modal.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-004.

**Expected results:**
- Tabs, validation states, badge, modal and HTMX fit Violet standard.
- correct breadcrumbs, HTMX and responsive Violet error state.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-ING-005 — Metrics/Alertmanager or Source Binding points to wrong cluster/instance

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; cross-cluster Metrics/Alertmanager binding mismatch.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Metrics/Alertmanager or Source Binding points to wrong cluster/instance.
2. Perform the scenario action using an approved domain/service test client: Metrics/Alertmanager or Source Binding points to wrong cluster/instance.
3. attempt binding foreign provider then inspect consumer correlation.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-005.

**Expected results:**
- Reject cross-scope binding rather than fallback to default or another source.
- no default provider fallback or foreign source admission.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

## Notification Channels & Activity Center

**Owner:** app/platform_operations/notifications/; app/integrations/delivery/.  
**Candidate pytest/Playwright suites:** tests/integrations/notification_channels/; tests/contracts/integrations/; tests/ui/.  

### UAT-NTF-001 — Authorized operator configures supported notification channel

**Type:** Positive · **Layer:** Both · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Controlled channel fixture; disabled/failed delivery, permissions and stable event ID; supported isolated notification channel and permitted actor.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Authorized operator configures supported notification channel.
2. Perform the scenario action using an approved browser or domain test client: Authorized operator configures supported notification channel.
3. configure/validate instance and inspect delivery eligibility.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-001.

**Expected results:**
- Safe configuration status, validation/audit and correct delivery eligibility.
- channel readiness and audit reflect authoritative test response.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/notification_channels/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-NTF-002 — Delivery fails and retry/dedup encounters same event key

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Controlled channel fixture; disabled/failed delivery, permissions and stable event ID; deterministically failing delivery and one canonical event key.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Delivery fails and retry/dedup encounters same event key.
2. Perform the scenario action using an approved domain/service test client: Delivery fails and retry/dedup encounters same event key.
3. retry/replay identical event key and inspect delivery history.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-002.

**Expected results:**
- No false Delivered state, duplicate flooding or unbounded retry.
- bounded dedup avoids flooding and no false Delivered.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/notification_channels/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-NTF-003 — Channel disabled or unsupported provider is selected

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Controlled channel fixture; disabled/failed delivery, permissions and stable event ID; disabled channel and unsupported provider fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Channel disabled or unsupported provider is selected.
2. Perform the scenario action using an approved browser or domain test client: Channel disabled or unsupported provider is selected.
3. attempt delivery for both and inspect selected transport.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-003.

**Expected results:**
- Send is blocked or correctly marked ineligible; no silent fallback.
- ineligible status recorded without silent fallback.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/notification_channels/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

### UAT-NTF-004 — Notification Center tabs, filters, details and read-only activity links

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Controlled channel fixture; disabled/failed delivery, permissions and stable event ID; Notification Center fixtures with error/read/unread and multiple rows.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Notification Center tabs, filters, details and read-only activity links.
2. Perform the scenario action using an approved browser or domain test client: Notification Center tabs, filters, details and read-only activity links.
3. change filters/Rows, open detail and clear filters.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-004.

**Expected results:**
- Correct pagination, accurate status, accessible interactive disclosure.
- event status and pagination remain accurate and accessible.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/integrations/notification_channels/; tests/contracts/integrations/; tests/ui/.; do not infer coverage from filename.

## Intelligence — Recommendations, Alerts, Catalog & Automation Control

**Owner:** app/intelligence/README.md.  
**Candidate pytest/Playwright suites:** tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/.  

### UAT-INL-001 — Operator views recommendation and drilldown to impacted asset

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; committed cross-domain finding with source fingerprint and asset.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator views recommendation and drilldown to impacted asset.
2. Perform the scenario action using an approved browser or domain test client: Operator views recommendation and drilldown to impacted asset.
3. navigate recommendation to impacted asset and source detail.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-001.

**Expected results:**
- Finding uses current committed evidence, exact source, scope and severity.
- scope/severity/source correspond to committed evidence.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/.; do not infer coverage from filename.

### UAT-INL-002 — Finding source expires, clears or changes fingerprint

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; finding whose source expires or fingerprint changes.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Finding source expires, clears or changes fingerprint.
2. Perform the scenario action using an approved domain/service test client: Finding source expires, clears or changes fingerprint.
3. refresh evidence then revisit finding and action.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-002.

**Expected results:**
- Old finding/advice cannot be presented as fresh authoritative risk.
- obsolete advice is marked stale/superseded, not authoritative.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/.; do not infer coverage from filename.

### UAT-INL-003 — Unauthorized/unapproved actor attempts high-impact automation

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; unapproved high-impact resolver and maker/approver identities.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Unauthorized/unapproved actor attempts high-impact automation.
2. Perform the scenario action using an approved browser or domain test client: Unauthorized/unapproved actor attempts high-impact automation.
3. attempt authorization bypass and self-approval via direct request.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-003.

**Expected results:**
- Maker-checker/default-deny prevents execution and unauthorized escalation.
- default deny prevents resolver/provider execution.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/.; do not infer coverage from filename.

### UAT-INL-004 — Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; published rules, recommendations, alert and control catalog fixtures.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs.
2. Perform the scenario action using an approved browser or domain test client: Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs.
3. navigate tabs and inspect disabled controls at mobile width.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-004.

**Expected results:**
- Accurate active/disabled/read-only states; HTMX, light/dark and responsive layout.
- governance state and HTMX/theme/accessibility remain consistent.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/.; do not infer coverage from filename.

### UAT-INL-005 — Alert normalization has partial or unavailable provider evidence

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; partial provider alert payload and duplicate normalized keys.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Alert normalization has partial or unavailable provider evidence.
2. Perform the scenario action using an approved domain/service test client: Alert normalization has partial or unavailable provider evidence.
3. normalize both signals and inspect correlation output.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-005.

**Expected results:**
- Unknown cannot be shown Healthy; duplicate cases and invented correlation prevented.
- unknown remains unknown and duplicates are not invented edges.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/.; do not infer coverage from filename.

## Reports — Generate, Generated, Templates, Schedules & Storage

**Owner:** app/reports/README.md; docs/reports/kaori-reporting-standard-v1.md.  
**Candidate pytest/Playwright suites:** tests/reports/; tests/contracts/reports/; tests/ui/.  

### UAT-RPT-001 — Report generation respects exact selected source and format

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue, one registered supported infrastructure source, disposable output bucket/path, permitted user.

**Steps:**
1. Open Reports → Generate as permitted test principal.
2. Select one exact source scope and supported report family and output format.
3. Submit request; capture queued job, completion and generated artifact metadata.
4. Inspect actual PDF/XLSX/CSV structure and source identity where suitable.

**Expected results:**
- Job is admitted once under canonical Reports execution; no wrong-source fallback.
- Generated artifact type and content match selected scope/format.
- Generated registry and storage metadata show correct state, size and safe access.

**Required evidence:** Browser trace, JobExecution/correlation, artifact metadata, test renderer assertions and cleanup.

**Isolation / cleanup:** Isolated Reports worker/storage; remove generated test artifacts safely.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

### UAT-RPT-002 — Invalid output type, unselected cluster or unsupported report catalog requested

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; unsupported format/type and absent required cluster fixtures.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Invalid output type, unselected cluster or unsupported report catalog requested.
2. Perform the scenario action using an approved browser or domain test client: Invalid output type, unselected cluster or unsupported report catalog requested.
3. submit wizard and same malformed direct HTTP request.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-002.

**Expected results:**
- Reject; never silently switch cluster/type/renderer.
- no report/job row and no silent renderer/scope switching.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

### UAT-RPT-003 — Reports worker/storage failure does not show generated success

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Disposable Reports queue/storage test environment with controlled worker unavailable or storage write failure.

**Steps:**
1. Select valid bounded report request from the UI.
2. Simulate worker unavailable, renderer failure or storage rejection through isolated test fixture.
3. Open Generated Reports and Jobs to inspect requested and terminal states.
4. Compare artifact existence, JobExecution and Activity outcome.

**Expected results:**
- No generated artifact falsely listed as ready/downloadable.
- Error/blocked feedback truthfully identifies the failure while protecting internals.
- Job/audit state and storage record are consistent and retry is explicit if permitted.

**Required evidence:** UI loading/error screenshots, worker logs (sanitized), JobExecution, artifact store absence and metadata.

**Isolation / cleanup:** Do not stop live Reports workers or delete real artifact storage.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

### UAT-RPT-004 — Generate wizard interacts with selectors, validation and progress

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; five-step wizard with configured source and storage readiness.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Generate wizard interacts with selectors, validation and progress.
2. Perform the scenario action using an approved browser or domain test client: Generate wizard interacts with selectors, validation and progress.
3. change scope/output/sections then force validation error on Review.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-004.

**Expected results:**
- Expected step navigation, editable fields, loading/blocked/toast and responsive layout.
- focus, editable state and loading/blocked toast remain accessible.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

### UAT-RPT-005 — Unauthorized principal opens Generated artifact or storage linkage

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; private generated artifact owned by another scoped principal.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Unauthorized principal opens Generated artifact or storage linkage.
2. Perform the scenario action using an approved domain/service test client: Unauthorized principal opens Generated artifact or storage linkage.
3. request detail and download directly without authorization.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-005.

**Expected results:**
- Permission-scope checks prevent disclosure even by direct URL.
- no file bytes, link/token or private metadata disclosure.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

### UAT-RPT-006 — Schedule modified/deleted after run admitted

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; admitted scheduled run snapshot and editable source schedule.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Schedule modified/deleted after run admitted.
2. Perform the scenario action using an approved domain/service test client: Schedule modified/deleted after run admitted.
3. change/delete schedule before worker reads accepted run.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-006.

**Expected results:**
- Run uses committed snapshot of accepted delivery intent, not mutable definition.
- run uses immutable original scope and delivery intent.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

### UAT-RPT-007 — Browse Generated, Templates, Schedules and Storage registries

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; Generated/Templates/Schedules/Storage registries with >5 rows.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Browse Generated, Templates, Schedules and Storage registries.
2. Perform the scenario action using an approved browser or domain test client: Browse Generated, Templates, Schedules and Storage registries.
3. filter/page each registry, open detail and inspect download state.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-007.

**Expected results:**
- Scoped filters/pagination, detail handoff, evidence state, downloadable artifact metadata.
- scoped pagination and artifact readiness remain truthful.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/reports/; tests/contracts/reports/; tests/ui/.; do not infer coverage from filename.

## Platform Operations — Overview, Jobs & Executions

**Owner:** app/platform_operations/README.md; app/platform_operations/jobs/.  
**Candidate pytest/Playwright suites:** tests/platform_operations/jobs/; tests/contracts/platform_operations/; tests/ui/.  

### UAT-OPS-001 — Operator views Jobs registry, selects failed execution and reads details

**Type:** Positive · **Layer:** Both · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Known JobExecution history, policy scopes and isolated queue worker fixtures; failed JobExecution with known owner and error correlation.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator views Jobs registry, selects failed execution and reads details.
2. Perform the scenario action using an approved browser or domain test client: Operator views Jobs registry, selects failed execution and reads details.
3. filter Jobs by failure and navigate to owning capability.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-001.

**Expected results:**
- Correct job owner, state, error evidence and link to owning capability.
- job state, owner and error evidence remain consistent.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/platform_operations/jobs/; tests/contracts/platform_operations/; tests/ui/.; do not infer coverage from filename.

### UAT-OPS-002 — Job retry/cancel occurs during worker result race

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Known JobExecution history, policy scopes and isolated queue worker fixtures; in-flight job and concurrent cancellation/retry fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Job retry/cancel occurs during worker result race.
2. Perform the scenario action using an approved domain/service test client: Job retry/cancel occurs during worker result race.
3. race terminal worker result with cancel/retry action.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-002.

**Expected results:**
- No duplicate forbidden execution or false terminal status.
- no duplicate forbidden execution or terminal status overwrite.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/platform_operations/jobs/; tests/contracts/platform_operations/; tests/ui/.; do not infer coverage from filename.

### UAT-OPS-003 — Worker/queue dependency unavailable or blocked

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Known JobExecution history, policy scopes and isolated queue worker fixtures; unavailable queue/worker with historical JobExecution.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Worker/queue dependency unavailable or blocked.
2. Perform the scenario action using an approved browser or domain test client: Worker/queue dependency unavailable or blocked.
3. attempt a new job and inspect Overview/Jobs degraded state.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-003.

**Expected results:**
- Correct blocked/degraded visibility, no invented execution success.
- no invented success and historical jobs remain attributable.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/platform_operations/jobs/; tests/contracts/platform_operations/; tests/ui/.; do not infer coverage from filename.

### UAT-OPS-004 — Platform Overview and Jobs tabs/filters/actions are exercised

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Known JobExecution history, policy scopes and isolated queue worker fixtures; committed Platform summary and permission-scoped jobs.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Platform Overview and Jobs tabs/filters/actions are exercised.
2. Perform the scenario action using an approved browser or domain test client: Platform Overview and Jobs tabs/filters/actions are exercised.
3. filter overview/jobs then switch to restricted mobile actor.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-004.

**Expected results:**
- Committed-only summary, appropriate permission scopes and canonical visual states.
- committed summary and action visibility obey RBAC.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/platform_operations/jobs/; tests/contracts/platform_operations/; tests/ui/.; do not infer coverage from filename.

## Platform Operations — Data Lifecycle & Secret Reveal

**Owner:** app/platform_operations/data_lifecycle/; app/platform_operations/kubernetes/.  
**Candidate pytest/Playwright suites:** tests/contracts/platform_operations/; tests/platform_operations/; tests/security/kubernetes/.  

### UAT-LIF-001 — Operator previews lifecycle policy and executes approved archive-first run

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; approved archive destination and disposable retention candidates.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator previews lifecycle policy and executes approved archive-first run.
2. Perform the scenario action using an approved browser or domain test client: Operator previews lifecycle policy and executes approved archive-first run.
3. preview, archive, verify and only then clean approved items.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-001.

**Expected results:**
- Verified archival evidence precedes governed cleanup; JobExecution/audit consistent.
- archive checksum and JobExecution predate cleanup.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/platform_operations/; tests/platform_operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-LIF-002 — Unverified archive blocks retention cleanup

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Dedicated disposable lifecycle records and archive sink configured to fail verification; cleanup path isolated.

**Steps:**
1. Prepare a policy and candidate lifecycle records in sandbox.
2. Cause archive destination/read-back verification to fail deterministically.
3. Attempt the governed lifecycle execution; inspect job, archive and UI outcome.
4. Verify original records remain present and no cleanup is reported successful.

**Expected results:**
- No destructive purge of unverified data.
- Job/Archive/Audit evidence shows failure or blocked action, not success.
- Operator is given safe recovery/next action without silently retrying destruction.

**Required evidence:** Record IDs pre/post, archive read-back, JobExecution, failed verification and UI error state.

**Isolation / cleanup:** Never inject failure into live retention/purge, production backups or non-disposable records.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/platform_operations/; tests/platform_operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-LIF-003 — Unapproved/expired reveal request tries to access secret

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; expired reveal approval and restricted test principal.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Unapproved/expired reveal request tries to access secret.
2. Perform the scenario action using an approved browser or domain test client: Unapproved/expired reveal request tries to access secret.
3. attempt UI and direct endpoint reveal after expiration.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-003.

**Expected results:**
- Fail closed; only authorized one-time disclosure, never routine leakage.
- no secret bytes, success claim or approval bypass.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/platform_operations/; tests/platform_operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-LIF-004 — Kubernetes Admin Overview and Secret Reveal workspace navigation

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** An authorized Kubernetes Admin operator and selected Kubernetes X300 cluster; The global Secret Reveal gate is deployment-managed and read-only in this workspace. Record role, cluster context and source SHA.

**Steps:**
1. The operator opens the Kubernetes Admin Overview.
2. Opens Secret Reveal, Cluster Prerequisites, then Namespace Policies.
3. Reloads a direct policies deep link.
4. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- Canonical Hero, committed coverage and Secret Reveal configuration render.
- Tab, selected cluster and policy-view context survive navigation and browser refresh.
- Credential readiness and operator attestations remain readable without exposing Secret payloads.
- Inline namespace policy editors remain collapsed until explicitly opened.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. Relevant manual observation and acceptance commentary: #2605, #2457 or #1384; that does not attribute a machine Scenario-ID PASS.

**Isolation / cleanup:** Use authorized test principals and the documented cluster source; restore browser filters/editor state. No unintended Secret or provider writes.

**Automation mapping:** Existing candidate suites: `tests/contracts/platform_operations/test_kubernetes_admin_htmx_summary_contract.py; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-005 — Lifecycle attempt duplicates during policy update or failure

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; running destructive lifecycle job and concurrent policy change.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Lifecycle attempt duplicates during policy update or failure.
2. Perform the scenario action using an approved browser or domain test client: Lifecycle attempt duplicates during policy update or failure.
3. submit duplicate plan and inject worker failure.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-005.

**Expected results:**
- No duplicate destructive job or false archived/cleaned claim.
- no repeated delete or false archive/cleanup status.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/platform_operations/; tests/platform_operations/; tests/security/kubernetes/.; do not infer coverage from filename.

### UAT-LIF-006 — Namespace Policy pagination, search and filters retain canonical state

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** A selected cluster with 25 live namespaces and two enabled policies. Record role, cluster context and source SHA.

**Steps:**
1. The operator moves to page 2 then page 3 of the five-row Namespace Policies table.
2. Uses Previous to return to page 2 and refreshes the browser.
3. Searches for harbor, clears filters, and selects Enabled only.
4. Changes Rows Per Page from 5 to 10.
5. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- Numbered pagination preserves its selected page across HTMX updates and reload.
- Search and Enabled only scope the matching live namespace policies correctly.
- The header says 25 Total Namespaces while the footer counts current filter matches.
- Ten-row pagination has three pages without opening policy editors.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. Relevant manual observation and acceptance commentary: #2605, #2457 or #1384; that does not attribute a machine Scenario-ID PASS.

**Isolation / cleanup:** Use authorized test principals and the documented cluster source; restore browser filters/editor state. No unintended Secret or provider writes.

**Automation mapping:** Existing candidate suites: `tests/contracts/platform_operations/test_kubernetes_admin_htmx_summary_contract.py; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-007 — Cancel discards an unsaved namespace policy change

**Type:** Negative · **Layer:** UI · **Risk:** Medium · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** The committed minio namespace policy is Step-up authentication. Record role, cluster context and source SHA.

**Steps:**
1. The operator opens Edit Policy for minio.
2. Changes the proposed policy to Disabled without clicking Save Policy.
3. Clicks Cancel and refreshes the page.
4. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- The inline editor closes with no committed change.
- The original Step-up authentication policy and enabled namespace count remain unchanged.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. Relevant manual observation and acceptance commentary: #2605, #2457 or #1384; that does not attribute a machine Scenario-ID PASS.

**Isolation / cleanup:** Use authorized test principals and the documented cluster source; restore browser filters/editor state. No unintended Secret or provider writes.

**Automation mapping:** Existing candidate suites: `tests/contracts/platform_operations/test_kubernetes_admin_htmx_summary_contract.py; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-008 — Approved Harbor policy save and rollback preserve audit correlation

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** A permitted operator expressly authorizes a nonproduction harbor policy test; Harbor is Available with a Disabled policy and no impacted pending reveal requests. Record role, cluster context and source SHA.

**Steps:**
1. The operator saves Approval required for harbor.
2. Confirms the new policy and committed Activity Audit evidence.
3. Immediately saves Disabled to restore the original policy.
4. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- The enabled namespace count rises from two to three and returns to two.
- The first audit event records disabled to approval_required.
- The second audit event records approval_required to disabled.
- Both event keys and actor attribution remain correct without exposing Secret payloads.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. Relevant manual observation and acceptance commentary: #2605, #2457 or #1384; that does not attribute a machine Scenario-ID PASS.

**Isolation / cleanup:** Only the explicitly approved nonproduction Harbor namespace; confirm no pending or approved reveal requests will expire. Restore its original Disabled policy immediately; never reveal a Secret.

**Automation mapping:** Existing candidate suites: `tests/platform_operations/test_secret_reveal_htmx_save.py; tests/contracts/platform_operations/test_kubernetes_admin_atomic_activity_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-009 — Viewer direct requests cannot read Kubernetes Admin configuration

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** A Viewer without Kubernetes Secret Reveal management permission. Record role, cluster context and source SHA.

**Steps:**
1. The Viewer requests the Kubernetes Admin Overview URL directly.
2. Requests the Secret Reveal workspace URL directly.
3. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- The server denies both unauthorized read requests.
- The KAORI Access Denied page explains the role and access administrator contact.
- No cluster credential or namespace policy data is disclosed.
- A permitted administrator can later read the unchanged configuration.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. Relevant manual observation and acceptance commentary: #2605, #2457 or #1384; that does not attribute a machine Scenario-ID PASS.

**Isolation / cleanup:** Use authorized test principals and the documented cluster source; restore browser filters/editor state. No unintended Secret or provider writes.

**Automation mapping:** Existing candidate suites: `tests/contracts/platform_operations/test_kubernetes_admin_htmx_summary_contract.py; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-010 — Unauthorized or missing-CSRF policy POST cannot commit changes

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** Isolated test identities and a known committed namespace policy. Record role, cluster context and source SHA.

**Steps:**
1. A Viewer attempts a direct namespace policy POST.
2. A permitted test principal posts without a valid CSRF token.
3. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- The server rejects each unauthorized request.
- No policy update or successful Activity Audit event is committed.
- The original policy and Secret confidentiality are preserved.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. This negative/visual case was NOT RUN during the bounded manual Kubernetes Admin UAT.

**Isolation / cleanup:** Use isolated fixtures and a deterministic simulated provider failure; do not issue unauthorized live writes or invalidate production readiness.

**Automation mapping:** Existing candidate suites: `tests/contracts/platform_operations/test_kubernetes_admin_htmx_summary_contract.py; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-011 — Unavailable namespace source and unready clusters fail closed

**Type:** Negative · **Layer:** Both · **Risk:** High · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** An isolated cluster with controllable Namespace provider availability and readiness. Record role, cluster context and source SHA.

**Steps:**
1. The Namespace provider cannot confirm live namespace presence.
2. An operator attempts policy enablement on an unavailable namespace or unready cluster.
3. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- Source Unknown is distinct from an authoritatively Missing namespace.
- The enablement attempt fails closed without pretending runtime access is verified.
- No Secret value or unauthorized policy change is exposed.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. This negative/visual case was NOT RUN during the bounded manual Kubernetes Admin UAT.

**Isolation / cleanup:** Use isolated fixtures and a deterministic simulated provider failure; do not issue unauthorized live writes or invalidate production readiness.

**Automation mapping:** Existing candidate suites: `tests/contracts/platform_operations/test_kubernetes_admin_htmx_summary_contract.py; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-012 — Audit Warning presents successful namespace restriction as attention

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** Committed Activity Audit events for an approved harbor policy change and rollback. Record role, cluster context and source SHA.

**Steps:**
1. The auditor opens the Success policy enable event.
2. Opens the Warning policy disable event.
3. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- The Success record retains its before and after changes and event key.
- The Warning record shows Attention Summary and Review Guidance.
- No failure claim or retry instruction is displayed for a successful disable.
- A genuine Error event still presents Failure Summary and Next Review Step.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. Relevant manual observation and acceptance commentary: #2605, #2457 or #1384; that does not attribute a machine Scenario-ID PASS.

**Isolation / cleanup:** Read-only review of already committed Activity Audit records; never replay a mutation just to create evidence.

**Automation mapping:** Existing candidate suites: `tests/contracts/access/test_activity_audit_outcome_first_detail_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

### UAT-LIF-013 — Kubernetes Admin responsive visual and keyboard coverage

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Expanded QA specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING (per scenario ID; #2605 Human Accepted the bounded UAT workstream)

**Preconditions:** The approved KAORI Violet light and dark design system and six canonical viewports. Record role, cluster context and source SHA.

**Steps:**
1. The operator navigates workspace tabs, policy filters and inline editors by keyboard.
2. Inspects loading, blocked and no-results states across the supported viewports.
3. Inspect the resulting UI, authoritative committed state and source-owned audit evidence without exposing credentials..

**Expected results:**
- Focus order and accessible control labels remain correct.
- No action, table or guidance is clipped in light or dark mode.
- Visual baselines are not silently accepted or regenerated.

**Required evidence:** Sanitized browser state before/after action and exact candidate SHA; HTTP/JUnit/Playwright trace if automated; committed policy and Activity Audit record for mutation or explicit negative absence for denied paths. This negative/visual case was NOT RUN during the bounded manual Kubernetes Admin UAT.

**Isolation / cleanup:** Use existing stable UI fixtures and the canonical Visual QA harness; do not rebaseline without human review.

**Automation mapping:** Existing candidate suites: `tests/ui/; tests/contracts/platform_operations/test_kubernetes_admin_namespace_filter_a11y_contract.py`. Individual assertion-to-ID mapping and machine execution **not validated**; do not invent an executable UAT PASS.

## Welcome Workspace Catalog

**Owner:** app/welcome/; app/templates/welcome/; app/templates/components/.  
**Candidate pytest/Playwright suites:** tests/welcome/; tests/security/welcome/; tests/rendering/welcome/; tests/e2e/welcome/; tests/ui/.  
**Manual evidence authority:** #746 (2026-10-23/24 operator acceptance and screenshots); machine execution remains NOT RUN for these new Scenario IDs.

### UAT-WEL-001 — Authenticated users reach the canonical Welcome landing

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** An active signed-in test principal; exact source SHA, role and session origin recorded; external providers isolated.

**Steps:**
1. Request / and /welcome in the same authenticated browser session.
2. Inspect response status, role metadata, Hero, Workspace Catalog, and app shell.
3. Verify page rendering uses only authorized catalog metadata and no provider request in the landing route.

**Expected results:**
- Both routes render authenticated Welcome with correct identity/role and authorized workspace cards.
- The landing remains provider-free; no infrastructure metric/health data is fetched by Welcome.

**Required evidence:** Exact candidate SHA, effective role/permissions where relevant, browser response and DOM assertions, Playwright screenshots/trace/JUnit where applicable, screenshot theme/viewport and reviewed baseline identity; manual #746 UAT recorded independently.

**Isolation / cleanup:** Use isolated disposable users, a deterministic browser and provider-free landing boundary; restore session/theme/filter state after tests. Do not mutate production providers or approve visual baselines automatically.

**Automation mapping:** Partial: tests/e2e/welcome/test_welcome_smoke.py::test_authenticated_user_can_render_welcome_with_global_application_shell, app/welcome/routes.py (source-reviewed). Provider-free enforcement is a source/design contract, not a live provider-execution test.

### UAT-WEL-002 — Welcome only renders workspaces authorized for the active role

**Type:** Positive · **Layer:** Both · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Disposable Super Admin and default Viewer identities, their effective role grants, current shortcut definitions, and independent sessions.

**Steps:**
1. Open /welcome as Super Admin; capture cards, group counts and response HTML.
2. Open /welcome as Viewer in a fresh session; read actual rendered HTML before client filtering.
3. Compare each authorized destination and group/count with permission-to-endpoint definitions; inspect unauthorized metadata absence.
4. Confirm universal personal Settings remains discoverable and target routes independently authorize.

**Expected results:**
- Visible and server-rendered workspaces correspond to role permissions with correct counts and no duplicate cards.
- Viewer cannot discover Integrations, Platform Operations or Access with default role grants; forbidden card metadata is absent from HTML.
- Settings is available for every authenticated user; no permission is conferred by card visibility.

**Required evidence:** Exact candidate SHA, effective role/permissions where relevant, browser response and DOM assertions, Playwright screenshots/trace/JUnit where applicable, screenshot theme/viewport and reviewed baseline identity; manual #746 UAT recorded independently.

**Isolation / cleanup:** Use isolated disposable users, a deterministic browser and provider-free landing boundary; restore session/theme/filter state after tests. Do not mutate production providers or approve visual baselines automatically.

**Automation mapping:** Partial: tests/welcome/test_welcome_characterization.py and tests/security/welcome/test_welcome_security.py inspect catalog definition filtering. Exact default Viewer server-rendered HTML and role matrix browser assertions still require automated proof.

### UAT-WEL-003 — Tenant search filters authorized workspace cards

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Authenticated user with tenant.view, current Tenant Management card rendered, idle browser with searchable catalog.

**Steps:**
1. Locate the Search Workspaces control and focus it using the keyboard shortcut /.
2. Fill tenant; observe the rendered cards, per-group counts and polite result counter.
3. Inspect search DOM for unrelated/unauthorized cards and verify document width.

**Expected results:**
- Only the Tenant Management card remains visible with result count 1 Workspace.
- Unmatched capability groups are hidden and the authorized DOM does not gain permissions or request provider data.

**Required evidence:** Exact candidate SHA, effective role/permissions where relevant, browser response and DOM assertions, Playwright screenshots/trace/JUnit where applicable, screenshot theme/viewport and reviewed baseline identity; manual #746 UAT recorded independently.

**Isolation / cleanup:** Use isolated disposable users, a deterministic browser and provider-free landing boundary; restore session/theme/filter state after tests. Do not mutate production providers or approve visual baselines automatically.

**Automation mapping:** Source-reviewed: tests/ui/test_representative_interactions.py::test_welcome_catalog_content_search_and_card_geometry_across_canonical_viewports. Actual pytest/Playwright execution not observed.

### UAT-WEL-004 — Unmatched search shows an empty state and Escape restores the catalog

**Type:** Negative · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Authenticated user with a nonempty authorized catalog, keyboard-enabled browser and a search term not present in rendered workspace metadata.

**Steps:**
1. Capture original authorized card/group counts.
2. Type a guaranteed unmatched query and inspect result count, hidden groups/cards and canonical no-results state.
3. While the search input is focused, press Escape.
4. Verify the query is cleared, focus leaves the input, all original cards/groups return and counts restore.

**Expected results:**
- Unmatched search shows exactly 0 Workspaces and No Permitted Workspace Matches This Search.
- Escape restores only the original permitted catalog and does not leak unauthorized destinations or leave focus trapped.

**Required evidence:** Exact candidate SHA, effective role/permissions where relevant, browser response and DOM assertions, Playwright screenshots/trace/JUnit where applicable, screenshot theme/viewport and reviewed baseline identity; manual #746 UAT recorded independently.

**Isolation / cleanup:** Use isolated disposable users, a deterministic browser and provider-free landing boundary; restore session/theme/filter state after tests. Do not mutate production providers or approve visual baselines automatically.

**Automation mapping:** Partial: existing Playwright Welcome test checks Escape restoration following tenant filter; static template/JS contracts inspect empty state. The full unmatched-query browser transition is not yet directly asserted.

### UAT-WEL-005 — Welcome remains usable across canonical viewports and persisted themes

**Type:** Positive · **Layer:** UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reviewed KAORI Violet layout/visual baselines, built frontend assets, existing Playwright fixtures, six canonical viewport sizes and persisted-theme setup.

**Steps:**
1. Render light and dark theme at 1440x900, 1280x800, 1024x768, 768x1024, 390x844 and 360x800.
2. Inspect Hero/Access Scope, catalog search, all capability groups, card contents and Open Workspace actions including bottom-of-page scroll.
3. Run the existing geometry and governed screenshot-baseline assertions; capture screenshots/trace and any mismatch.
4. Leave approved visual-baseline fingerprints unchanged unless a separate explicit human visual acceptance approves the exact intentional delta.

**Expected results:**
- No document-width overflow, clipped cards, overlapping text or unreachable actions; expected responsive reflow and theme persistence remain intact.
- Baseline mismatch remains FAIL pending review rather than silent regeneration.

**Required evidence:** Exact candidate SHA, effective role/permissions where relevant, browser response and DOM assertions, Playwright screenshots/trace/JUnit where applicable, screenshot theme/viewport and reviewed baseline identity; manual #746 UAT recorded independently.

**Isolation / cleanup:** Use isolated disposable users, a deterministic browser and provider-free landing boundary; restore session/theme/filter state after tests. Do not mutate production providers or approve visual baselines automatically.

**Automation mapping:** Source-reviewed: tests/ui/test_representative_interactions.py::test_welcome_visual_qa_light_and_dark and ::test_welcome_catalog_content_search_and_card_geometry_across_canonical_viewports; tests/ui/visual_audit.py. Full-scroll cards/accessibility are not equivalent to viewport screenshot-only assertions.

### UAT-WEL-006 — An authorized workspace card navigates to its protected destination

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Authenticated principal with a permission allowing at least one Welcome destination; route under test is implemented and enabled.

**Steps:**
1. Select a permitted workspace card and record its server-resolved href.
2. Activate Open Workspace through a real browser click, not direct hidden DOM mutation.
3. Assert the route responds with the intended destination and expected breadcrumb/heading.
4. Recheck destination permission guard using separate restricted principal or owning endpoint test.

**Expected results:**
- The selected card lands in its capability-owned route with the correct page context.
- Destination authorization remains independent from Welcome discoverability, without privilege expansion.

**Required evidence:** Exact candidate SHA, effective role/permissions where relevant, browser response and DOM assertions, Playwright screenshots/trace/JUnit where applicable, screenshot theme/viewport and reviewed baseline identity; manual #746 UAT recorded independently.

**Isolation / cleanup:** Use isolated disposable users, a deterministic browser and provider-free landing boundary; restore session/theme/filter state after tests. Do not mutate production providers or approve visual baselines automatically.

**Automation mapping:** Partial: Welcome target resolution is covered by tests/unit/welcome/test_welcome_target_resolution.py and catalog characterization; browser click-through to an authorized destination is not directly established by the inspected Welcome smoke.

## Shared Shell, Settings, Visual QA & Accessibility

**Owner:** docs/standards/KAORI_ENGINEERING_STANDARD_V1.md; #222; #543.  
**Candidate pytest/Playwright suites:** tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.  

### UAT-UIX-001 — Login and navigate sidebar, tabs, breadcrumb and global actions

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; authenticated shell, mobile drawer and working deep links.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Login and navigate sidebar, tabs, breadcrumb and global actions.
2. Perform the scenario action using an approved browser or domain test client: Login and navigate sidebar, tabs, breadcrumb and global actions.
3. use sidebar/tab/breadcrumb and browser history with keyboard.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-001.

**Expected results:**
- Correct active destination, responsive drawer, keyboard accessibility and history.
- correct active destination, focus and accessible drawer.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

### UAT-UIX-002 — Modal remains accessible at 360×800 after validation

**Type:** Negative · **Layer:** UI · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Authenticated browser fixture with a real form/modal in an available KAORI capability; deterministic content and viewport 360×800.

**Steps:**
1. Open actual modal/drawer using Playwright click, not by injecting hidden CSS classes.
2. Fill invalid value; click submit to trigger validation and any HTMX replacement.
3. Assert dialog bounds, visible primary/secondary actions, focus/error association and no document horizontal overflow.
4. Capture screenshots before open, after open and after validation in light and dark where applicable.

**Expected results:**
- All accessible actions remain reachable; modal body scrolls when needed.
- No clipped Save/Cancel buttons, hidden validation text or focus lost behind overlay.
- No unauthorized form submission or successful toast when validation failed.

**Required evidence:** Playwright trace/screenshots, bounding boxes, keyboard navigation assertion and error state.

**Isolation / cleanup:** Deterministic test fixtures; do not auto-update baselines based on failed geometry.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

### UAT-UIX-003 — Switch light/dark and revisit page/overlay across canonical viewports

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; persisted light/dark theme and deterministic routes.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Switch light/dark and revisit page/overlay across canonical viewports.
2. Perform the scenario action using an approved browser or domain test client: Switch light/dark and revisit page/overlay across canonical viewports.
3. toggle theme, reload and open overlays at six viewports.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-003.

**Expected results:**
- Theme persisted, Violet/shared components and text contrast remain legible.
- theme persists and components remain legible.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

### UAT-UIX-004 — Geometry regressions fail instead of approving poor baseline

**Type:** Negative · **Layer:** UI · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Reviewed KAORI Violet/shared Hero/table baseline and deterministic example page including a controlled changed layout fixture.

**Steps:**
1. Render a real audited page with source-equivalent frontend CSS at 1440×900 and 390×844.
2. Apply a narrowly controlled fixture that causes Hero wrapping, clipped primary action, or modal overflow.
3. Run existing executable visual geometry assertions, then screenshot comparison.
4. Inspect evidence and restore fixture/baseline unchanged.

**Expected results:**
- Actual rendered geometry violation fails even if source-length/style checks pass.
- Screenshot/diff and precise invariant identify affected surface/viewport/theme.
- Reviewed baselines are preserved; no silent acceptance or arbitrary AI visual score.

**Required evidence:** Playwright assertion, original/actual screenshot, trace and baseline-diff finding.

**Isolation / cleanup:** No mutation to approved screenshot baselines in a normal test run.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

### UAT-UIX-005 — Empty/loading/error/blocked state and pending HTMX action appear

**Type:** Negative · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; controlled empty/loading/error/blocked HTMX responses.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Empty/loading/error/blocked state and pending HTMX action appear.
2. Perform the scenario action using an approved browser or domain test client: Empty/loading/error/blocked state and pending HTMX action appear.
3. trigger failed request then retry/recover through UI.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-005.

**Expected results:**
- Correct shared semantic state and recoverability; no misleading empty success.
- no false empty-success semantics and state is actionable.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

### UAT-UIX-006 — Change pagination rows 5→10, filter and Clear Filters

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; paginated >10 records with active filter.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Change pagination rows 5→10, filter and Clear Filters.
2. Perform the scenario action using an approved browser or domain test client: Change pagination rows 5→10, filter and Clear Filters.
3. select Rows ten, paginate then Clear Filters.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-006.

**Expected results:**
- Reset to page 1, preserve Rows and correct HTMX target and loading.
- page resets one, preserves Rows and HTMX target.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

### UAT-UIX-007 — Mandatory UI base URL or authenticated browser fixture is unavailable

**Type:** Negative · **Layer:** UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; missing browser base URL or authenticated fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Mandatory UI base URL or authenticated browser fixture is unavailable.
2. Perform the scenario action using an approved browser or domain test client: Mandatory UI base URL or authenticated browser fixture is unavailable.
3. invoke mandatory test under intentionally unavailable browser.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-007.

**Expected results:**
- Scenario reports SKIP/BLOCKED, not a UAT execution PASS.
- runner marks blocked/skip/not-run instead of PASS.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/.; do not infer coverage from filename.

## Release & Server UAT Operational Evidence

**Owner:** docs/engineering/KAORI_DELIVERY_WORKFLOW.md; #619; #1710.  
**Candidate pytest/Playwright suites:** tests/contracts/release/; tests/integration/release/.  

### UAT-REL-001 — Deploy exact accepted image and inspect health, workers and release identity

**Type:** Positive · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access; accepted staging SHA/tree and immutable registry digest.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Deploy exact accepted image and inspect health, workers and release identity.
2. Perform the scenario action using an approved domain/service test client: Deploy exact accepted image and inspect health, workers and release identity.
3. deploy approved image and inspect health, workers and migrations.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REL-001.

**Expected results:**
- Healthy readiness, matching SHA/digest, migration and rollback evidence.
- host digest and rollback/migration evidence match accepted candidate.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/release/; tests/integration/release/.; do not infer coverage from filename.

### UAT-REL-002 — Wrong OCI digest never deploys as accepted candidate

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Original first-wave procedure — verify against current candidate · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Existing accepted staging SHA/image digest identity, governed release evidence and safe mock/isolated deployment preflight. No production deploy.

**Steps:**
1. Construct a candidate request with mismatched SHA/digest or stale accepted candidate identity.
2. Run canonical delivery preflight/contract verifier only against isolated fixtures.
3. Compare permitted release/deploy intent and previous accepted release identity.
4. Inspect actionable rejection/error evidence.

**Expected results:**
- Request rejected before changing running image or marking UAT accepted.
- Current release digest, state and recovery authority unchanged.
- No invented PASS, promotion or release tag is recorded.

**Required evidence:** Preflight output, immutable candidate metadata assertions, rejected request and no-mutation proof.

**Isolation / cleanup:** Never manually dispatch deploy/release workflow for a negative test on real staging host.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/release/; tests/integration/release/.; do not infer coverage from filename.

### UAT-REL-003 — Migration/readiness/recovery precondition fails in controlled drill

**Type:** Negative · **Layer:** Non-UI · **Risk:** High · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access; controlled failed deployment readiness/migration fixture.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Migration/readiness/recovery precondition fails in controlled drill.
2. Perform the scenario action using an approved domain/service test client: Migration/readiness/recovery precondition fails in controlled drill.
3. perform bounded fail/restore drill and recheck host readiness.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REL-003.

**Expected results:**
- No false UAT PASS or release advance; restore/roll-forward evidence correct.
- no false UAT pass or release advance.
- The negative request does not create a misleading success state or an unauthorized committed/provider side effect.

**Required evidence:** pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/release/; tests/integration/release/.; do not infer coverage from filename.

### UAT-REL-004 — Operator performs bounded hosted-UI smoke on deployed UAT image

**Type:** Positive · **Layer:** UI · **Risk:** Medium · **Maturity:** Newly expanded specification — capability-owner review required · **Execution:** NOT RUN · **Human acceptance:** PENDING

**Preconditions:** Admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access; approved hosted UAT image and scoped test principal.

**Steps:**
1. Record the exact candidate, actor, scoped source identity and baseline state for: Operator performs bounded hosted-UI smoke on deployed UAT image.
2. Perform the scenario action using an approved browser or domain test client: Operator performs bounded hosted-UI smoke on deployed UAT image.
3. login and exercise key screens, modal and mobile state.
4. Inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REL-004.

**Expected results:**
- Login/navigation, critical screens, responsive states and user-visible feedback work.
- browser behavior and deployed digest match accepted release.
- The observed success is attributable to the selected source, authorized actor and correct committed identity.

**Required evidence:** browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.

**Isolation / cleanup:** Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.

**Automation mapping:** Not validated. Inspect assertions under tests/contracts/release/; tests/integration/release/.; do not infer coverage from filename.

## Review and execution truth

- 98 written test cases are specified; 84 require capability-owner review before acceptance.
- These files neither trigger CI/CD nor claim any pytest/Playwright, provider/UAT or human PASS.
- Unavailable or unadmitted functions must be marked BLOCKED and reviewed against current documentation; never invent provider behavior.
- Maintain exact scenario ID relationships across catalog, Gherkin, pytest/Playwright, execution evidence and human acceptance.

