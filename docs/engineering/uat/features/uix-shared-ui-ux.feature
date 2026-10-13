# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Shared Shell, Settings, Visual QA & Accessibility
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-UIX-001 @positive @medium @ui @draft @not_run
  Scenario: UAT-UIX-001 - Login and navigate sidebar, tabs, breadcrumb and global actions
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes
    When login and navigate sidebar, tabs, breadcrumb and global actions
    Then correct active destination, responsive drawer, keyboard accessibility and history

  # Scope: UI; risk: High; expanded first-wave steps.
  # Required evidence: Playwright trace/screenshots, bounding boxes, keyboard navigation assertion and error state.
  # Isolation: Deterministic test fixtures; do not auto-update baselines based on failed geometry.
  @UAT-UIX-002 @negative @high @ui @detailed @not_run
  Scenario: UAT-UIX-002 - Modal remains accessible at 360×800 after validation
    Given authenticated browser fixture with a real form/modal in an available KAORI capability
    And deterministic content and viewport 360×800
    When open actual modal/drawer using Playwright click, not by injecting hidden CSS classes
    And fill invalid value
    And click submit to trigger validation and any HTMX replacement
    And assert dialog bounds, visible primary/secondary actions, focus/error association and no document horizontal overflow
    And capture screenshots before open, after open and after validation in light and dark where applicable
    Then all accessible actions remain reachable; modal body scrolls when needed
    And no clipped Save/Cancel buttons, hidden validation text or focus lost behind overlay
    And no unauthorized form submission or successful toast when validation failed

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-UIX-003 @positive @medium @ui @draft @not_run
  Scenario: UAT-UIX-003 - Switch light/dark and revisit page/overlay across canonical viewports
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes
    When switch light/dark and revisit page/overlay across canonical viewports
    Then theme persisted, Violet/shared components and text contrast remain legible

  # Scope: UI; risk: High; expanded first-wave steps.
  # Required evidence: Playwright assertion, original/actual screenshot, trace and baseline-diff finding.
  # Isolation: No mutation to approved screenshot baselines in a normal test run.
  @UAT-UIX-004 @negative @high @ui @detailed @not_run
  Scenario: UAT-UIX-004 - Geometry regressions fail instead of approving poor baseline
    Given reviewed KAORI Violet/shared Hero/table baseline and deterministic example page including a controlled changed layout fixture
    When render a real audited page with source-equivalent frontend CSS at 1440×900 and 390×844
    And apply a narrowly controlled fixture that causes Hero wrapping, clipped primary action, or modal overflow
    And run existing executable visual geometry assertions, then screenshot comparison
    And inspect evidence and restore fixture/baseline unchanged
    Then actual rendered geometry violation fails even if source-length/style checks pass
    And screenshot/diff and precise invariant identify affected surface/viewport/theme
    And reviewed baselines are preserved; no silent acceptance or arbitrary AI visual score

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-UIX-005 @negative @medium @ui @draft @not_run
  Scenario: UAT-UIX-005 - Empty/loading/error/blocked state and pending HTMX action appear
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes
    When empty/loading/error/blocked state and pending HTMX action appear
    Then correct shared semantic state and recoverability; no misleading empty success

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-UIX-006 @positive @medium @ui @draft @not_run
  Scenario: UAT-UIX-006 - Change pagination rows 5→10, filter and Clear Filters
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes
    When change pagination rows 5→10, filter and Clear Filters
    Then reset to page 1, preserve Rows and correct HTMX target and loading

  # Scope: UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-UIX-007 @negative @high @ui @draft @not_run
  Scenario: UAT-UIX-007 - Mandatory UI base URL or authenticated browser fixture is unavailable
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes
    When mandatory UI base URL or authenticated browser fixture is unavailable
    Then scenario reports SKIP/BLOCKED, not a UAT execution PASS

