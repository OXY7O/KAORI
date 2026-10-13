# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Kubernetes — Dashboard, Inventory & Topology
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-INV-001 @positive @medium @ui @draft @not_run
  Scenario: UAT-INV-001 - Operator opens Cluster/Dashboard then Inventory lists and details
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects
    When operator opens Cluster/Dashboard then Inventory lists and details
    Then correct selected-cluster scope, navigation, row/detail identity and shared table UI

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INV-002 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-INV-002 - Inventory evidence is stale, missing or partially collected
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects
    When inventory evidence is stale, missing or partially collected
    Then uI explicitly displays stale/partial/unknown, not fabricated Healthy/zero

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INV-003 @negative @high @non_ui @draft @not_run
  Scenario: UAT-INV-003 - Same-name object is recreated with a different provider UID
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects
    When same-name object is recreated with a different provider UID
    Then old/new identities are not conflated; lineage and correlation remain correct

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-INV-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-INV-004 - Filter/sort/page Inventory records including zero-result state
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects
    When filter/sort/page Inventory records including zero-result state
    Then filters persist across HTMX navigation; pagination and No Results follow shared standard

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-INV-005 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-INV-005 - Topology relationship source is absent or inconsistent
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects
    When topology relationship source is absent or inconsistent
    Then no invented dependency edges or misleading cross-cluster relationship

