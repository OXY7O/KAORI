# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Artifact Registry — Inventory, Security, Runtime & Governance
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-REG-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-REG-001 - Operator inspects registry/artifact inventory and synchronized evidence
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved
    When operator inspects registry/artifact inventory and synchronized evidence
    Then correct registry/project/artifact/version identity, freshness and pagination

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-REG-002 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-REG-002 - Security vulnerability scan is absent, failed or partial
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved
    When security vulnerability scan is absent, failed or partial
    Then unknown/partial posture not labeled Secure/Healthy

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Normalized binding assertion, source fingerprint, UI detail screenshot, trace and empty/degraded state.
  # Isolation: Read-only fixture; no registry image or cluster resource mutation.
  @UAT-REG-003 @negative @high @ui @non_ui @detailed @not_run
  Scenario: UAT-REG-003 - Stale artifact-to-runtime identity cannot claim verified binding
    Given two distinct registry/runtime identities or stale runtime snapshot fixture
    And no provider writes required
    When record artifact registry identity and currently committed runtime binding evidence
    And make target cluster/runtime evidence stale, missing or identity-mismatched in fixture
    And open Runtime Usage/Topology details and inspect binding status
    And check underlying normalized correlation status against source fingerprint
    Then uI labels missing/unverified/stale binding truthfully, not verified/Ready
    And no false artifact-to-runtime link or cross-cluster association is committed
    And uI remains navigable and usable in error/unknown state at supported viewports

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-REG-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-REG-004 - User opens Runtime Usage topology/detail and applies scoped filters
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved
    When user opens Runtime Usage topology/detail and applies scoped filters
    Then links/tabs/modal and filter states work with canonical responsive layout

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-REG-005 @negative @high @non_ui @draft @not_run
  Scenario: UAT-REG-005 - Registry provider disabled or sync failed after earlier success
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved
    When registry provider disabled or sync failed after earlier success
    Then latest committed source state truthfully supersedes old Ready evidence

