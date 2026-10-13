# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Platform Operations — Data Lifecycle & Secret Reveal
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-LIF-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-LIF-001 - Operator previews lifecycle policy and executes approved archive-first run
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; approved archive destination and disposable retention candidates
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator previews lifecycle policy and executes approved archive-first run
    And perform the scenario action using an approved browser or domain test client: Operator previews lifecycle policy and executes approved archive-first run
    And preview, archive, verify and only then clean approved items
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-001
    Then verified archival evidence precedes governed cleanup; JobExecution/audit consistent
    And archive checksum and JobExecution predate cleanup
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Record IDs pre/post, archive read-back, JobExecution, failed verification and UI error state.
  # Isolation: Never inject failure into live retention/purge, production backups or non-disposable records.
  @UAT-LIF-002 @negative @high @non_ui @specified @first_wave
  Scenario: UAT-LIF-002 - Unverified archive blocks retention cleanup
    Given dedicated disposable lifecycle records and archive sink configured to fail verification; cleanup path isolated
    And the actor permission, selected source and original state are recorded
    When prepare a policy and candidate lifecycle records in sandbox
    And cause archive destination/read-back verification to fail deterministically
    And attempt the governed lifecycle execution; inspect job, archive and UI outcome
    And verify original records remain present and no cleanup is reported successful
    Then no destructive purge of unverified data
    And job/Archive/Audit evidence shows failure or blocked action, not success
    And operator is given safe recovery/next action without silently retrying destruction

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-LIF-003 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-LIF-003 - Unapproved/expired reveal request tries to access secret
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; expired reveal approval and restricted test principal
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Unapproved/expired reveal request tries to access secret
    And perform the scenario action using an approved browser or domain test client: Unapproved/expired reveal request tries to access secret
    And attempt UI and direct endpoint reveal after expiration
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-003
    Then fail closed; only authorized one-time disclosure, never routine leakage
    And no secret bytes, success claim or approval bypass
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-LIF-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-LIF-004 - Kubernetes Admin Overview → Secret Reveal tab and policy forms
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; safe policy fixtures and Kubernetes Admin Secret Reveal tab
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Kubernetes Admin Overview → Secret Reveal tab and policy forms
    And perform the scenario action using an approved browser or domain test client: Kubernetes Admin Overview → Secret Reveal tab and policy forms
    And open deep link via HTMX then validate and save policy
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-004
    Then hTMX lazy loading, deep links, accessible modal and save feedback work
    And correct tab, errors, toast and persisted policy
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-LIF-005 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-LIF-005 - Lifecycle attempt duplicates during policy update or failure
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization; running destructive lifecycle job and concurrent policy change
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Lifecycle attempt duplicates during policy update or failure
    And perform the scenario action using an approved browser or domain test client: Lifecycle attempt duplicates during policy update or failure
    And submit duplicate plan and inject worker failure
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-LIF-005
    Then no duplicate destructive job or false archived/cleaned claim
    And no repeated delete or false archive/cleanup status
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

