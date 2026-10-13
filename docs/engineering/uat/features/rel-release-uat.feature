# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Release & Server UAT Operational Evidence
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-REL-001 @positive @high @non_ui @draft @not_run
  Scenario: UAT-REL-001 - Deploy exact accepted image and inspect health, workers and release identity
    Given admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access
    When deploy exact accepted image and inspect health, workers and release identity
    Then healthy readiness, matching SHA/digest, migration and rollback evidence

  # Scope: Non-UI; risk: High; expanded first-wave steps.
  # Required evidence: Preflight output, immutable candidate metadata assertions, rejected request and no-mutation proof.
  # Isolation: Never manually dispatch deploy/release workflow for a negative test on real staging host.
  @UAT-REL-002 @negative @high @non_ui @detailed @not_run
  Scenario: UAT-REL-002 - Wrong OCI digest never deploys as accepted candidate
    Given existing accepted staging SHA/image digest identity, governed release evidence and safe mock/isolated deployment preflight. No production deploy
    When construct a candidate request with mismatched SHA/digest or stale accepted candidate identity
    And run canonical delivery preflight/contract verifier only against isolated fixtures
    And compare permitted release/deploy intent and previous accepted release identity
    And inspect actionable rejection/error evidence
    Then request rejected before changing running image or marking UAT accepted
    And current release digest, state and recovery authority unchanged
    And no invented PASS, promotion or release tag is recorded

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-REL-003 @negative @high @non_ui @draft @not_run
  Scenario: UAT-REL-003 - Migration/readiness/recovery precondition fails in controlled drill
    Given admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access
    When migration/readiness/recovery precondition fails in controlled drill
    Then no false UAT PASS or release advance; restore/roll-forward evidence correct

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-REL-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-REL-004 - Operator performs bounded hosted-UI smoke on deployed UAT image
    Given admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access
    When operator performs bounded hosted-UI smoke on deployed UAT image
    Then login/navigation, critical screens, responsive states and user-visible feedback work

