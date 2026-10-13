# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Platform Operations — Data Lifecycle & Secret Reveal
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-LIF-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-LIF-001 - Operator previews lifecycle policy and executes approved archive-first run
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization
    When operator previews lifecycle policy and executes approved archive-first run
    Then verified archival evidence precedes governed cleanup; JobExecution/audit consistent

  # Scope: Non-UI; risk: High; expanded first-wave steps.
  # Required evidence: Record IDs pre/post, archive read-back, JobExecution, failed verification and UI error state.
  # Isolation: Never inject failure into live retention/purge, production backups or non-disposable records.
  @UAT-LIF-002 @negative @high @non_ui @detailed @not_run
  Scenario: UAT-LIF-002 - Unverified archive blocks retention cleanup
    Given dedicated disposable lifecycle records and archive sink configured to fail verification
    And cleanup path isolated
    When prepare a policy and candidate lifecycle records in sandbox
    And cause archive destination/read-back verification to fail deterministically
    And attempt the governed lifecycle execution
    And inspect job, archive and UI outcome
    And verify original records remain present and no cleanup is reported successful
    Then no destructive purge of unverified data
    And job/Archive/Audit evidence shows failure or blocked action, not success
    And operator is given safe recovery/next action without silently retrying destruction

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-LIF-003 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-LIF-003 - Unapproved/expired reveal request tries to access secret
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization
    When unapproved/expired reveal request tries to access secret
    Then fail closed; only authorized one-time disclosure, never routine leakage

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-LIF-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-LIF-004 - Kubernetes Admin Overview → Secret Reveal tab and policy forms
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization
    When kubernetes Admin Overview → Secret Reveal tab and policy forms
    Then hTMX lazy loading, deep links, accessible modal and save feedback work

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-LIF-005 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-LIF-005 - Lifecycle attempt duplicates during policy update or failure
    Given archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization
    When lifecycle attempt duplicates during policy update or failure
    Then no duplicate destructive job or false archived/cleaned claim

