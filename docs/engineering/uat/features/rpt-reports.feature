# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# Reusable specification only: runtime outcomes and human decisions live in execution records.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Reports — Generate, Generated, Templates, Schedules & Storage
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Browser trace, JobExecution/correlation, artifact metadata, test renderer assertions and cleanup.
  # Isolation: Isolated Reports worker/storage; remove generated test artifacts safely.
  @UAT-RPT-001 @positive @high @ui @non_ui @detailed
  Scenario: UAT-RPT-001 - Report generation respects exact selected source and format
    Given reports worker/queue, one registered supported infrastructure source, disposable output bucket/path, permitted user
    When open Reports → Generate as permitted test principal
    And select one exact source scope and supported report family and output format
    And submit request
    And capture queued job, completion and generated artifact metadata
    And inspect actual PDF/XLSX/CSV structure and source identity where suitable
    Then job is admitted once under canonical Reports execution; no wrong-source fallback
    And generated artifact type and content match selected scope/format
    And generated registry and storage metadata show correct state, size and safe access

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-RPT-002 @negative @high @ui @non_ui @draft
  Scenario: UAT-RPT-002 - Invalid output type, unselected cluster or unsupported report catalog requested
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup
    When invalid output type, unselected cluster or unsupported report catalog requested
    Then reject; never silently switch cluster/type/renderer

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: UI loading/error screenshots, worker logs (sanitized), JobExecution, artifact store absence and metadata.
  # Isolation: Do not stop live Reports workers or delete real artifact storage.
  @UAT-RPT-003 @negative @high @ui @non_ui @detailed
  Scenario: UAT-RPT-003 - Reports worker/storage failure does not show generated success
    Given disposable Reports queue/storage test environment with controlled worker unavailable or storage write failure
    When select valid bounded report request from the UI
    And simulate worker unavailable, renderer failure or storage rejection through isolated test fixture
    And open Generated Reports and Jobs to inspect requested and terminal states
    And compare artifact existence, JobExecution and Activity outcome
    Then no generated artifact falsely listed as ready/downloadable
    And error/blocked feedback truthfully identifies the failure while protecting internals
    And job/audit state and storage record are consistent and retry is explicit if permitted

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-RPT-004 @positive @medium @ui @draft
  Scenario: UAT-RPT-004 - Generate wizard interacts with selectors, validation and progress
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup
    When generate wizard interacts with selectors, validation and progress
    Then expected step navigation, editable fields, loading/blocked/toast and responsive layout

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-RPT-005 @negative @high @non_ui @draft
  Scenario: UAT-RPT-005 - Unauthorized principal opens Generated artifact or storage linkage
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup
    When unauthorized principal opens Generated artifact or storage linkage
    Then permission-scope checks prevent disclosure even by direct URL

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-RPT-006 @negative @high @non_ui @draft
  Scenario: UAT-RPT-006 - Schedule modified/deleted after run admitted
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup
    When schedule modified/deleted after run admitted
    Then run uses committed snapshot of accepted delivery intent, not mutable definition

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-RPT-007 @positive @medium @ui @draft
  Scenario: UAT-RPT-007 - Browse Generated, Templates, Schedules and Storage registries
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup
    When browse Generated, Templates, Schedules and Storage registries
    Then scoped filters/pagination, detail handoff, evidence state, downloadable artifact metadata

