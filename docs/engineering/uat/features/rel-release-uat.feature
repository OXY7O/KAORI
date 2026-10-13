# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Release & Server UAT Operational Evidence
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-REL-001 @positive @high @non_ui @specified @owner_review
  Scenario: UAT-REL-001 - Deploy exact accepted image and inspect health, workers and release identity
    Given admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access; accepted staging SHA/tree and immutable registry digest
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Deploy exact accepted image and inspect health, workers and release identity
    And perform the scenario action using an approved domain/service test client: Deploy exact accepted image and inspect health, workers and release identity
    And deploy approved image and inspect health, workers and migrations
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REL-001
    Then healthy readiness, matching SHA/digest, migration and rollback evidence
    And host digest and rollback/migration evidence match accepted candidate
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Preflight output, immutable candidate metadata assertions, rejected request and no-mutation proof.
  # Isolation: Never manually dispatch deploy/release workflow for a negative test on real staging host.
  @UAT-REL-002 @negative @high @non_ui @specified @first_wave
  Scenario: UAT-REL-002 - Wrong OCI digest never deploys as accepted candidate
    Given existing accepted staging SHA/image digest identity, governed release evidence and safe mock/isolated deployment preflight. No production deploy
    And the actor permission, selected source and original state are recorded
    When construct a candidate request with mismatched SHA/digest or stale accepted candidate identity
    And run canonical delivery preflight/contract verifier only against isolated fixtures
    And compare permitted release/deploy intent and previous accepted release identity
    And inspect actionable rejection/error evidence
    Then request rejected before changing running image or marking UAT accepted
    And current release digest, state and recovery authority unchanged
    And no invented PASS, promotion or release tag is recorded

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-REL-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-REL-003 - Migration/readiness/recovery precondition fails in controlled drill
    Given admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access; controlled failed deployment readiness/migration fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Migration/readiness/recovery precondition fails in controlled drill
    And perform the scenario action using an approved domain/service test client: Migration/readiness/recovery precondition fails in controlled drill
    And perform bounded fail/restore drill and recheck host readiness
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REL-003
    Then no false UAT PASS or release advance; restore/roll-forward evidence correct
    And no false UAT pass or release advance
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-REL-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-REL-004 - Operator performs bounded hosted-UI smoke on deployed UAT image
    Given admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access; approved hosted UAT image and scoped test principal
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator performs bounded hosted-UI smoke on deployed UAT image
    And perform the scenario action using an approved browser or domain test client: Operator performs bounded hosted-UI smoke on deployed UAT image
    And login and exercise key screens, modal and mobile state
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REL-004
    Then login/navigation, critical screens, responsive states and user-visible feedback work
    And browser behavior and deployed digest match accepted release
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

