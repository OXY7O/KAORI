# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Access — Users, Roles, Permissions & Identity Providers
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-IAM-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-IAM-001 - Permitted admin creates/updates user and role assignment
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; disposable target user, admin and allowed role
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Permitted admin creates/updates user and role assignment
    And perform the scenario action using an approved browser or domain test client: Permitted admin creates/updates user and role assignment
    And save a role assignment then reload directory and effective permission as new request
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-001
    Then persisted identity/role state, correct directory UI, safe Activity evidence
    And persisted memberships and actor/target audit match approved input
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Playwright response and screenshot, denied permission assertion, before/after persisted state.
  # Isolation: Do not test escalation on a production administrative identity.
  @UAT-IAM-002 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-IAM-002 - Restricted user cannot mutate Users or Roles through direct requests
    Given two local test principals with known disjoint role permissions and disposable User/Role fixtures
    And the actor permission, selected source and original state are recorded
    When sign in as a restricted user; confirm role mutation action is not falsely advertised
    And invoke a direct protected mutation URL/API as that user, including valid CSRF material when relevant
    And read User/Role records and Activity to inspect post-request state
    Then server rejects unauthorized access regardless of UI visibility
    And no role membership, privilege or administrative object changes
    And error response/UI is safe and does not leak sensitive role details

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-IAM-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-IAM-003 - Protected role or forbidden permission escalation is submitted
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; protected role and forbidden permission escalation fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Protected role or forbidden permission escalation is submitted
    And perform the scenario action using an approved domain/service test client: Protected role or forbidden permission escalation is submitted
    And post escalation directly, then reload effective roles under new session
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-003
    Then canonical RBAC guard rejects; no effective privilege expansion
    And guard denies and grants do not expand even if navigation is hidden
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-IAM-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-IAM-004 - Admin filters User Directory/Permission Catalog and clears filters
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; directory with 12 users and distinct permission catalog entries
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Admin filters User Directory/Permission Catalog and clears filters
    And perform the scenario action using an approved browser or domain test client: Admin filters User Directory/Permission Catalog and clears filters
    And filter, switch Rows 5 to 10 and clear filters after HTMX refresh
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-004
    Then canonical default five rows, page one reset, selected row count preserved
    And page resets to one and chosen Rows remains ten
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-IAM-005 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-IAM-005 - Identity Provider is disabled, invalid or unreachable during auth
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; disabled or unreachable disposable identity provider
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Identity Provider is disabled, invalid or unreachable during auth
    And perform the scenario action using an approved browser or domain test client: Identity Provider is disabled, invalid or unreachable during auth
    And attempt provider login then direct protected URL and inspect fallback
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-005
    Then no fallback that admits an unauthorized identity; error state identifies dependency
    And no alternative authentication path admits the failed external principal
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-IAM-006 @negative @medium @ui @specified @owner_review
  Scenario: UAT-IAM-006 - Role/user modal or validation form receives missing and malformed fields
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture; empty and malformed fields on a disposable role/user modal
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Role/user modal or validation form receives missing and malformed fields
    And perform the scenario action using an approved browser or domain test client: Role/user modal or validation form receives missing and malformed fields
    And submit twice and inspect validation focus and persisted entity count
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-IAM-006
    Then actionable inline error; no partial entity creation; focus retained
    And accessible errors remain visible; no partial entity is created
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; distinct from UAT-IAM-002 protected mutation denial.
  # Evidence: actual GET document response status 403, denied UI and safe HTML/response.
  # Isolation: Disposable Viewer principal; no administrative operation or credential material.
  @UAT-IAM-007 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-IAM-007 - Viewer cannot open Access Overview through a direct read request
    Given an authenticated Viewer without any Access Overview permission
    When the user directly requests GET "/access/"
    Then the server responds with HTTP 403
    And the KAORI Access Denied page explains the permission boundary
    And guidance identifies the administrator contact path and safe Welcome navigation
    And protected Access Overview data is not returned
    And no administrative state is modified
