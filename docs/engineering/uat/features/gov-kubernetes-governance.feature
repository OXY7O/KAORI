# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Kubernetes — Governance & TLS
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-GOV-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-GOV-001 - Operator reviews TLS certificate inventory and governance finding
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox
    When operator reviews TLS certificate inventory and governance finding
    Then certificate identity, expiry/source and readiness reflect authoritative evidence

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-GOV-002 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-GOV-002 - TLS rotation preflight fails (identity/permission/impact)
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox
    When tLS rotation preflight fails (identity/permission/impact)
    Then change is blocked; original Secret/cert remains unchanged

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-GOV-003 @negative @high @non_ui @draft @not_run
  Scenario: UAT-GOV-003 - Capacity/quota or policy evidence is expired or conflicting
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox
    When capacity/quota or policy evidence is expired or conflicting
    Then mutation admission fails closed; no optimistic capacity claims

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-GOV-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-GOV-004 - Operator moves from governance finding to source evidence
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox
    When operator moves from governance finding to source evidence
    Then scoped navigation, accessible details and consistent blocked/error states

