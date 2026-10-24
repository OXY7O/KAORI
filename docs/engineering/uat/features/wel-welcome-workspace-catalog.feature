# KAORI UAT — Welcome Workspace Catalog acceptance specifications
# Authority: #1738 catalog, #746 Welcome UAT and #1725 QA evidence contract.
# Scenarios specify reusable expectations; existing pytest/Playwright remains the executor.
# Operator screenshots/HTTP 403 are manual UAT evidence on #746, not machine execution here.

Feature: Welcome Workspace Catalog
  Welcome is a permission-filtered authenticated landing page, not an infrastructure dashboard.
  Workspace discoverability must not grant access to a protected destination.

  Background:
    Given the exact KAORI source candidate and authenticated role fixture are identified
    And permission grants, workspace definitions and browser viewport are controlled
    And evidence is associated with that candidate rather than an unrelated UAT screenshot

  # Layer: UI; risk: Medium; existing Welcome E2E smoke offers partial candidate mapping.
  # Evidence: HTTP response, rendered shell and screenshot; no live-provider request.
  @UAT-WEL-001 @positive @medium @ui @specified @owner_review
  Scenario: UAT-WEL-001 - Authenticated users reach the canonical Welcome landing
    Given an authenticated KAORI user with an active role
    When the user requests both "/" and "/welcome"
    Then both routes return the authenticated Welcome workspace
    And the current identity, role and authorized workspace catalog are shown
    And the landing request does not query a live infrastructure provider

  # Layer: Both; risk: High; permission discoverability and raw HTML require server assertion.
  # Evidence: actual Viewer effective permissions, HTML response, card list, scopes and counts.
  @UAT-WEL-002 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-WEL-002 - Welcome only renders workspaces authorized for the active role
    Given a default Viewer and an administrator with known effective permission sets
    When each user requests the server-rendered Welcome page independently
    Then each workspace card and capability group matches that user's allowed targets
    And the displayed workspace count equals the authorized card count
    And the Viewer HTML contains no unauthorized Integrations, Platform Operations or Access card
    And personal Settings remains accessible to every authenticated role
    And permissions are checked again by each destination route

  # Layer: UI; risk: Medium; existing canonical Playwright coverage exercises tenant search.
  # Evidence: post-input DOM, visible group/card count, screenshot and trace.
  @UAT-WEL-003 @positive @medium @ui @specified @owner_review
  Scenario: UAT-WEL-003 - Tenant search filters authorized workspace cards
    Given an authenticated role permitted to view Tenant Management
    And the initial Welcome catalog is fully rendered
    When the user types "tenant" into Search Workspaces
    Then only the Tenant Management card is visible
    And the visible result counter reads "1 Workspace"
    And unrelated capability groups are hidden without exposing unauthorized metadata

  # Layer: UI; risk: Medium; no-match browser assertion needs explicit regression mapping.
  # Evidence: no-result screenshot, count and restored cards, keyboard focus after Escape.
  @UAT-WEL-004 @negative @medium @ui @specified @owner_review
  Scenario: UAT-WEL-004 - Unmatched search shows an empty state and Escape restores the catalog
    Given an authenticated user with a nonempty authorized Welcome catalog
    When the user searches for a term absent from all permitted workspaces
    Then the counter reads "0 Workspaces"
    And the canonical No Results empty state appears
    And no capability group or workspace card remains visible
    When the user presses Escape while the search field has focus
    Then the search query is cleared and focus leaves the input
    And all originally authorized workspace cards and counts are restored

  # Layer: UI; risk: High; reuse #543 six-viewports/two-themes baseline and geometry checks.
  # Evidence: screenshot/trace, viewport and theme state; no automatic baseline replacement.
  @UAT-WEL-005 @positive @high @ui @specified @owner_review
  Scenario: UAT-WEL-005 - Welcome remains usable across canonical viewports and persisted themes
    Given reviewed KAORI Violet layout contracts and source-controlled visual baselines
    When Welcome is rendered in light and dark at all six canonical viewport sizes
    And the full catalog is inspected including 390x844 and 360x800 mobile widths
    Then Hero, Access Scope, search, capability groups and cards preserve reading order
    And all visible Open Workspace actions remain reachable without horizontal overflow
    And card descriptions, labels and controls do not clip or overlap
    And any visual-baseline difference fails pending explicit human review

  # Layer: UI; risk: Medium; card-to-route click-through not established by prior smoke alone.
  # Evidence: clicked href, response authorization and returned destination route.
  @UAT-WEL-006 @positive @medium @ui @specified @owner_review
  Scenario: UAT-WEL-006 - An authorized workspace card navigates to its protected destination
    Given an authenticated user granted access to a destination exposed in Welcome
    When the user activates that card's Open Workspace link
    Then the link opens the intended capability-owned destination
    And the destination independently enforces its server-side permission boundary
    And the navigation does not grant any additional workspace entitlement
