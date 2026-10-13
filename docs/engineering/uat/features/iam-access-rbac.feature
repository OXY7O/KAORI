# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Access — Users, Roles, Permissions & Identity Providers
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-IAM-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-IAM-001 - Permitted admin creates/updates user and role assignment
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture
    When permitted admin creates/updates user and role assignment
    Then persisted identity/role state, correct directory UI, safe Activity evidence

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Playwright response and screenshot, denied permission assertion, before/after persisted state.
  # Isolation: Do not test escalation on a production administrative identity.
  @UAT-IAM-002 @negative @high @ui @non_ui @detailed @not_run
  Scenario: UAT-IAM-002 - Restricted user cannot mutate Users or Roles through direct requests
    Given two local test principals with known disjoint role permissions and disposable User/Role fixtures
    When sign in as a restricted user
    And confirm role mutation action is not falsely advertised
    And invoke a direct protected mutation URL/API as that user, including valid CSRF material when relevant
    And read User/Role records and Activity to inspect post-request state
    Then server rejects unauthorized access regardless of UI visibility
    And no role membership, privilege or administrative object changes
    And error response/UI is safe and does not leak sensitive role details

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-IAM-003 @negative @high @non_ui @draft @not_run
  Scenario: UAT-IAM-003 - Protected role or forbidden permission escalation is submitted
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture
    When protected role or forbidden permission escalation is submitted
    Then canonical RBAC guard rejects; no effective privilege expansion

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-IAM-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-IAM-004 - Admin filters User Directory/Permission Catalog and clears filters
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture
    When admin filters User Directory/Permission Catalog and clears filters
    Then canonical default five rows, page one reset, selected row count preserved

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-IAM-005 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-IAM-005 - Identity Provider is disabled, invalid or unreachable during auth
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture
    When identity Provider is disabled, invalid or unreachable during auth
    Then no fallback that admits an unauthorized identity; error state identifies dependency

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-IAM-006 @negative @medium @ui @draft @not_run
  Scenario: UAT-IAM-006 - Role/user modal or validation form receives missing and malformed fields
    Given operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture
    When role/user modal or validation form receives missing and malformed fields
    Then actionable inline error; no partial entity creation; focus retained

