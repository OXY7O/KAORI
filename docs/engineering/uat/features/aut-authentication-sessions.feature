# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Authentication & Sessions
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-AUT-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-AUT-001 - Valid active user logs in
    Given local test user, session fixtures and configured auth method; never expose real credentials; active user with known permission and a protected capability
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Valid active user logs in
    And perform the scenario action using an approved browser or domain test client: Valid active user logs in
    And open that protected capability after submitting correct credentials, then inspect session and Activity
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-001
    Then authenticated session, authorized navigation and correct audit/feedback are produced
    And session principal and permitted navigation agree; one authentication success is attributable
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Browser trace, sanitized response, session/access assertion and server-side auth result.
  # Isolation: Never publish credential input or auth cookie in CI traces.
  @UAT-AUT-002 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-AUT-002 - Invalid login never admits a session
    Given a test account exists; a known invalid password can be supplied. Use only disposable credentials
    And the actor permission, selected source and original state are recorded
    When open the canonical sign-in page with Playwright
    And fill username and invalid password; click submit
    And attempt to navigate directly to a protected capability URL and inspect server session state
    Then no authenticated session or protected content is granted
    And the form displays an actionable, non-enumerating authentication failure
    And no token, password or private identity data appears in screenshot/trace/audit

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-AUT-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-AUT-003 - Expired/revoked session submits a protected request
    Given local test user, session fixtures and configured auth method; never expose real credentials; an admitted session whose version can be revoked or expired
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Expired/revoked session submits a protected request
    And perform the scenario action using an approved domain/service test client: Expired/revoked session submits a protected request
    And reuse the earlier cookie for a protected direct POST after revocation
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-003
    Then server rejects request regardless of previously rendered UI
    And server independently denies access and does not create a new session or commit a mutation
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-AUT-004 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-AUT-004 - CSRF token is missing/invalid on a protected mutation
    Given local test user, session fixtures and configured auth method; never expose real credentials; disposable protected mutation and known valid CSRF form
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: CSRF token is missing/invalid on a protected mutation
    And perform the scenario action using an approved browser or domain test client: CSRF token is missing/invalid on a protected mutation
    And retry once with no token and once with a mismatched token
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-004
    Then mutation rejected with no committed/provider side effects
    And neither attempt changes persisted or provider state or produces a success Activity event
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; session/RBAC decision and persisted identity/activity.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-AUT-005 @positive @medium @ui @specified @owner_review
  Scenario: UAT-AUT-005 - User signs out and uses Back or bookmarked authenticated URL
    Given local test user, session fixtures and configured auth method; never expose real credentials; valid authenticated session and bookmarked protected URL
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: User signs out and uses Back or bookmarked authenticated URL
    And perform the scenario action using an approved browser or domain test client: User signs out and uses Back or bookmarked authenticated URL
    And log out, press Back, and request bookmarked URL again
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-AUT-005
    Then session ended, protected content cannot be recovered without login
    And fresh protected response is denied and browser history does not restore authorization
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

