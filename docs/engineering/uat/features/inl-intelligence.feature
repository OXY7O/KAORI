# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Intelligence — Recommendations, Alerts, Catalog & Automation Control
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INL-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-INL-001 - Operator views recommendation and drilldown to impacted asset
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved
    When operator views recommendation and drilldown to impacted asset
    Then finding uses current committed evidence, exact source, scope and severity

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INL-002 @negative @high @non_ui @draft @not_run
  Scenario: UAT-INL-002 - Finding source expires, clears or changes fingerprint
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved
    When finding source expires, clears or changes fingerprint
    Then old finding/advice cannot be presented as fresh authoritative risk

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INL-003 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-INL-003 - Unauthorized/unapproved actor attempts high-impact automation
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved
    When unauthorized/unapproved actor attempts high-impact automation
    Then maker-checker/default-deny prevents execution and unauthorized escalation

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-INL-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-INL-004 - Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved
    When navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs
    Then accurate active/disabled/read-only states; HTMX, light/dark and responsive layout

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INL-005 @negative @high @non_ui @draft @not_run
  Scenario: UAT-INL-005 - Alert normalization has partial or unavailable provider evidence
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved
    When alert normalization has partial or unavailable provider evidence
    Then unknown cannot be shown Healthy; duplicate cases and invented correlation prevented

