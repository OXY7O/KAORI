# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Shared Shell, Settings, Visual QA & Accessibility
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-UIX-001 @positive @medium @ui @specified @owner_review
  Scenario: UAT-UIX-001 - Login and navigate sidebar, tabs, breadcrumb and global actions
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; authenticated shell, mobile drawer and working deep links
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Login and navigate sidebar, tabs, breadcrumb and global actions
    And perform the scenario action using an approved browser or domain test client: Login and navigate sidebar, tabs, breadcrumb and global actions
    And use sidebar/tab/breadcrumb and browser history with keyboard
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-001
    Then correct active destination, responsive drawer, keyboard accessibility and history
    And correct active destination, focus and accessible drawer
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: UI; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Playwright trace/screenshots, bounding boxes, keyboard navigation assertion and error state.
  # Isolation: Deterministic test fixtures; do not auto-update baselines based on failed geometry.
  @UAT-UIX-002 @negative @high @ui @specified @first_wave
  Scenario: UAT-UIX-002 - Modal remains accessible at 360×800 after validation
    Given authenticated browser fixture with a real form/modal in an available KAORI capability; deterministic content and viewport 360×800
    And the actor permission, selected source and original state are recorded
    When open actual modal/drawer using Playwright click, not by injecting hidden CSS classes
    And fill invalid value; click submit to trigger validation and any HTMX replacement
    And assert dialog bounds, visible primary/secondary actions, focus/error association and no document horizontal overflow
    And capture screenshots before open, after open and after validation in light and dark where applicable
    Then all accessible actions remain reachable; modal body scrolls when needed
    And no clipped Save/Cancel buttons, hidden validation text or focus lost behind overlay
    And no unauthorized form submission or successful toast when validation failed

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-UIX-003 @positive @medium @ui @specified @owner_review
  Scenario: UAT-UIX-003 - Switch light/dark and revisit page/overlay across canonical viewports
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; persisted light/dark theme and deterministic routes
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Switch light/dark and revisit page/overlay across canonical viewports
    And perform the scenario action using an approved browser or domain test client: Switch light/dark and revisit page/overlay across canonical viewports
    And toggle theme, reload and open overlays at six viewports
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-003
    Then theme persisted, Violet/shared components and text contrast remain legible
    And theme persists and components remain legible
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: UI; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Playwright assertion, original/actual screenshot, trace and baseline-diff finding.
  # Isolation: No mutation to approved screenshot baselines in a normal test run.
  @UAT-UIX-004 @negative @high @ui @specified @first_wave
  Scenario: UAT-UIX-004 - Geometry regressions fail instead of approving poor baseline
    Given reviewed KAORI Violet/shared Hero/table baseline and deterministic example page including a controlled changed layout fixture
    And the actor permission, selected source and original state are recorded
    When render a real audited page with source-equivalent frontend CSS at 1440×900 and 390×844
    And apply a narrowly controlled fixture that causes Hero wrapping, clipped primary action, or modal overflow
    And run existing executable visual geometry assertions, then screenshot comparison
    And inspect evidence and restore fixture/baseline unchanged
    Then actual rendered geometry violation fails even if source-length/style checks pass
    And screenshot/diff and precise invariant identify affected surface/viewport/theme
    And reviewed baselines are preserved; no silent acceptance or arbitrary AI visual score

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-UIX-005 @negative @medium @ui @specified @owner_review
  Scenario: UAT-UIX-005 - Empty/loading/error/blocked state and pending HTMX action appear
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; controlled empty/loading/error/blocked HTMX responses
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Empty/loading/error/blocked state and pending HTMX action appear
    And perform the scenario action using an approved browser or domain test client: Empty/loading/error/blocked state and pending HTMX action appear
    And trigger failed request then retry/recover through UI
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-005
    Then correct shared semantic state and recoverability; no misleading empty success
    And no false empty-success semantics and state is actionable
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-UIX-006 @positive @medium @ui @specified @owner_review
  Scenario: UAT-UIX-006 - Change pagination rows 5→10, filter and Clear Filters
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; paginated >10 records with active filter
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Change pagination rows 5→10, filter and Clear Filters
    And perform the scenario action using an approved browser or domain test client: Change pagination rows 5→10, filter and Clear Filters
    And select Rows ten, paginate then Clear Filters
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-006
    Then reset to page 1, preserve Rows and correct HTMX target and loading
    And page resets one, preserves Rows and HTMX target
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-UIX-007 @negative @high @ui @specified @owner_review
  Scenario: UAT-UIX-007 - Mandatory UI base URL or authenticated browser fixture is unavailable
    Given deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes; missing browser base URL or authenticated fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Mandatory UI base URL or authenticated browser fixture is unavailable
    And perform the scenario action using an approved browser or domain test client: Mandatory UI base URL or authenticated browser fixture is unavailable
    And invoke mandatory test under intentionally unavailable browser
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-UIX-007
    Then scenario reports SKIP/BLOCKED, not a UAT execution PASS
    And runner marks blocked/skip/not-run instead of PASS
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

