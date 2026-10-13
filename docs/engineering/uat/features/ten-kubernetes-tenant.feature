# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Kubernetes — Tenant Management
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Pre/post provider identity and object diff, UI screenshot/trace, committed Tenant/Namespace fields and Audit correlation.
  # Isolation: Disposable Native Namespace only, read-back required and cleanup/recovery governed.
  @UAT-TEN-001 @positive @high @ui @non_ui @specified @first_wave
  Scenario: UAT-TEN-001 - Native Namespace adoption preserves provider authority
    Given approved disposable Native Namespace not owned by KAORI, baseline UID/resourceVersion, test operator with adoption permission; no Capsule ownership
    And the actor permission, selected source and original state are recorded
    When capture Kubernetes Namespace UID/resourceVersion, labels/owner references and applicable quota before test
    And navigate to Tenant Discovery/Adoption and select the exact Namespace
    And review Preflight and explicitly confirm the allowed adoption
    And inspect KAORI Tenant/Namespace committed record, generation and Activity; read back provider Namespace by exact UID
    Then exactly one adopted generation under correct cluster/provider/tenant scope
    And committed evidence identifies the verified provider object; no duplicate governance owner
    And only explicitly admitted provider writes occur; audit/mutation provenance is truthful

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Version before/after, browser trace, response, DB diff, provider diff and Audit.
  # Isolation: Use only approved test Namespace; do not create a conflict on real operational workloads.
  @UAT-TEN-002 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-TEN-002 - Stale Native Namespace preflight must fail closed
    Given approved disposable Native Namespace; controlled test fixture may change its resourceVersion between valid Preflight and submit
    And the actor permission, selected source and original state are recorded
    When record baseline provider UID, resourceVersion and KAORI adopted records
    And complete Discovery and Preflight through browser
    And change Namespace resourceVersion through an approved isolated fixture
    And submit the original stale form and inspect UI response, KAORI database and provider read-back
    Then no successful adoption; actionable error rather than success toast
    And no new adopted Tenant/Namespace generation and no unauthorized provider mutation
    And audit does not falsely claim successful adoption; failed attempt can be correlated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-TEN-003 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-TEN-003 - Create Tenant/Namespace from approved Resource Profile within budget
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; enabled versioned profile and disposable Native Tenant within fresh budget
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Create Tenant/Namespace from approved Resource Profile within budget
    And perform the scenario action using an approved browser or domain test client: Create Tenant/Namespace from approved Resource Profile within budget
    And submit Namespace provisioning then reread committed version and quota
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-003
    Then committed pinned profile version, allocation and provider read-back match
    And pinned profile and actual ResourceQuota/LimitRange match
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Form/preview screenshot, validation response, capacity source fingerprint, committed version and provider read-back.
  # Isolation: Never use a production allocation for boundary-failure testing.
  @UAT-TEN-004 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-TEN-004 - Capacity budget rejection prevents allocation mutation
    Given a disposable Tenant allocation/provisioning fixture with committed capacity evidence and a proposed change exceeding available governed headroom
    And the actor permission, selected source and original state are recorded
    When open Namespace Provisioning/Allocation Change as allowed operator
    And enter an allocation exceeding the accepted cluster budget
    And inspect preview/shortfall/readiness, then attempt submit via UI or direct request
    And compare committed allocation version and provider ResourceQuota/LimitRange before and after
    Then preview shows truthful shortfall and blocks mutation
    And server independently rejects an invalid/out-of-budget submit
    And pinned allocation and provider quota/limits remain unchanged with no success audit

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-TEN-005 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-TEN-005 - Restricted or self-approving actor attempts credential/Access Grant escalation
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; restricted tenant principal and independent approver roles
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Restricted or self-approving actor attempts credential/Access Grant escalation
    And perform the scenario action using an approved browser or domain test client: Restricted or self-approving actor attempts credential/Access Grant escalation
    And attempt credential/grant action and self-approval by direct request
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-005
    Then server denies or requires independent approval; secrets are not exposed
    And rBAC/maker-checker prevents unauthorized grant or secret exposure
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-TEN-006 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-TEN-006 - Provider patch succeeds but KAORI commit/read-back fails
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; sandbox Namespace with injected provider-patch then commit failure
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Provider patch succeeds but KAORI commit/read-back fails
    And perform the scenario action using an approved browser or domain test client: Provider patch succeeds but KAORI commit/read-back fails
    And capture UID/quota, fail persistence and reread provider residue
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-006
    Then no false complete state; recovery evidence identifies possible provider residue
    And failure/recovery evidence remains explicit and no Ready state is invented
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-TEN-007 @positive @medium @ui @specified @owner_review
  Scenario: UAT-TEN-007 - Resource Profile/Create/Allocation modal is opened and completed
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; disposable profile create/edit and Namespace allocation form
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Resource Profile/Create/Allocation modal is opened and completed
    And perform the scenario action using an approved browser or domain test client: Resource Profile/Create/Allocation modal is opened and completed
    And open controls, submit malformed then valid input, reread pinned version
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-007
    Then shared modal/input/validation, labels, toast and frozen allocation version rendered correctly
    And modal focus/toast/validation and frozen profile version are consistent
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-TEN-008 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-TEN-008 - Tenant released/re-adopted identity is reused or foreign Capsule owner appears
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities; recreated Namespace UID or foreign Capsule owner fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Tenant released/re-adopted identity is reused or foreign Capsule owner appears
    And perform the scenario action using an approved browser or domain test client: Tenant released/re-adopted identity is reused or foreign Capsule owner appears
    And attempt to adopt stale owner/generation then reread both identities
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-TEN-008
    Then fail closed against wrong generation/foreign owner; never silently take over
    And no takeover or historical generation rebinding occurs
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

