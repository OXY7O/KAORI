# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Intelligence — Recommendations, Alerts, Catalog & Automation Control
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INL-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-INL-001 - Operator views recommendation and drilldown to impacted asset
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; committed cross-domain finding with source fingerprint and asset
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator views recommendation and drilldown to impacted asset
    And perform the scenario action using an approved browser or domain test client: Operator views recommendation and drilldown to impacted asset
    And navigate recommendation to impacted asset and source detail
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-001
    Then finding uses current committed evidence, exact source, scope and severity
    And scope/severity/source correspond to committed evidence
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INL-002 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-INL-002 - Finding source expires, clears or changes fingerprint
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; finding whose source expires or fingerprint changes
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Finding source expires, clears or changes fingerprint
    And perform the scenario action using an approved domain/service test client: Finding source expires, clears or changes fingerprint
    And refresh evidence then revisit finding and action
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-002
    Then old finding/advice cannot be presented as fresh authoritative risk
    And obsolete advice is marked stale/superseded, not authoritative
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INL-003 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-INL-003 - Unauthorized/unapproved actor attempts high-impact automation
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; unapproved high-impact resolver and maker/approver identities
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Unauthorized/unapproved actor attempts high-impact automation
    And perform the scenario action using an approved browser or domain test client: Unauthorized/unapproved actor attempts high-impact automation
    And attempt authorization bypass and self-approval via direct request
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-003
    Then maker-checker/default-deny prevents execution and unauthorized escalation
    And default deny prevents resolver/provider execution
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-INL-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-INL-004 - Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; published rules, recommendations, alert and control catalog fixtures
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs
    And perform the scenario action using an approved browser or domain test client: Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs
    And navigate tabs and inspect disabled controls at mobile width
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-004
    Then accurate active/disabled/read-only states; HTMX, light/dark and responsive layout
    And governance state and HTMX/theme/accessibility remain consistent
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INL-005 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-INL-005 - Alert normalization has partial or unavailable provider evidence
    Given committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved; partial provider alert payload and duplicate normalized keys
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Alert normalization has partial or unavailable provider evidence
    And perform the scenario action using an approved domain/service test client: Alert normalization has partial or unavailable provider evidence
    And normalize both signals and inspect correlation output
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INL-005
    Then unknown cannot be shown Healthy; duplicate cases and invented correlation prevented
    And unknown remains unknown and duplicates are not invented edges
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

