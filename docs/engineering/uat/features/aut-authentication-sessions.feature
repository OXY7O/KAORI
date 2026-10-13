# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# Reusable specification only: runtime outcomes and human decisions live in execution records.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Authentication & Sessions
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-AUT-001 @positive @high @ui @non_ui @draft
  Scenario: UAT-AUT-001 - Valid active user logs in
    Given local test user, session fixtures and configured auth method; never expose real credentials
    When valid active user logs in
    Then authenticated session, authorized navigation and correct audit/feedback are produced

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Browser trace, sanitized response, session/access assertion and server-side auth result.
  # Isolation: Never publish credential input or auth cookie in CI traces.
  @UAT-AUT-002 @negative @high @ui @non_ui @detailed
  Scenario: UAT-AUT-002 - Invalid login never admits a session
    Given a test account exists
    And a known invalid password can be supplied. Use only disposable credentials
    When open the canonical sign-in page with Playwright
    And fill username and invalid password
    And click submit
    And attempt to navigate directly to a protected capability URL and inspect server session state
    Then no authenticated session or protected content is granted
    And the form displays an actionable, non-enumerating authentication failure
    And no token, password or private identity data appears in screenshot/trace/audit

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-AUT-003 @negative @high @non_ui @draft
  Scenario: UAT-AUT-003 - Expired/revoked session submits a protected request
    Given local test user, session fixtures and configured auth method; never expose real credentials
    When expired/revoked session submits a protected request
    Then server rejects request regardless of previously rendered UI

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-AUT-004 @negative @high @ui @non_ui @draft
  Scenario: UAT-AUT-004 - CSRF token is missing/invalid on a protected mutation
    Given local test user, session fixtures and configured auth method; never expose real credentials
    When cSRF token is missing/invalid on a protected mutation
    Then mutation rejected with no committed/provider side effects

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-AUT-005 @positive @medium @ui @draft
  Scenario: UAT-AUT-005 - User signs out and uses Back or bookmarked authenticated URL
    Given local test user, session fixtures and configured auth method; never expose real credentials
    When user signs out and uses Back or bookmarked authenticated URL
    Then session ended, protected content cannot be recovered without login

