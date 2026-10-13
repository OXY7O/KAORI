# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Reports — Generate, Generated, Templates, Schedules & Storage
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Browser trace, JobExecution/correlation, artifact metadata, test renderer assertions and cleanup.
  # Isolation: Isolated Reports worker/storage; remove generated test artifacts safely.
  @UAT-RPT-001 @positive @high @ui @non_ui @specified @first_wave
  Scenario: UAT-RPT-001 - Report generation respects exact selected source and format
    Given reports worker/queue, one registered supported infrastructure source, disposable output bucket/path, permitted user
    And the actor permission, selected source and original state are recorded
    When open Reports → Generate as permitted test principal
    And select one exact source scope and supported report family and output format
    And submit request; capture queued job, completion and generated artifact metadata
    And inspect actual PDF/XLSX/CSV structure and source identity where suitable
    Then job is admitted once under canonical Reports execution; no wrong-source fallback
    And generated artifact type and content match selected scope/format
    And generated registry and storage metadata show correct state, size and safe access

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-RPT-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-RPT-002 - Invalid output type, unselected cluster or unsupported report catalog requested
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; unsupported format/type and absent required cluster fixtures
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Invalid output type, unselected cluster or unsupported report catalog requested
    And perform the scenario action using an approved browser or domain test client: Invalid output type, unselected cluster or unsupported report catalog requested
    And submit wizard and same malformed direct HTTP request
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-002
    Then reject; never silently switch cluster/type/renderer
    And no report/job row and no silent renderer/scope switching
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: UI loading/error screenshots, worker logs (sanitized), JobExecution, artifact store absence and metadata.
  # Isolation: Do not stop live Reports workers or delete real artifact storage.
  @UAT-RPT-003 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-RPT-003 - Reports worker/storage failure does not show generated success
    Given disposable Reports queue/storage test environment with controlled worker unavailable or storage write failure
    And the actor permission, selected source and original state are recorded
    When select valid bounded report request from the UI
    And simulate worker unavailable, renderer failure or storage rejection through isolated test fixture
    And open Generated Reports and Jobs to inspect requested and terminal states
    And compare artifact existence, JobExecution and Activity outcome
    Then no generated artifact falsely listed as ready/downloadable
    And error/blocked feedback truthfully identifies the failure while protecting internals
    And job/audit state and storage record are consistent and retry is explicit if permitted

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-RPT-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-RPT-004 - Generate wizard interacts with selectors, validation and progress
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; five-step wizard with configured source and storage readiness
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Generate wizard interacts with selectors, validation and progress
    And perform the scenario action using an approved browser or domain test client: Generate wizard interacts with selectors, validation and progress
    And change scope/output/sections then force validation error on Review
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-004
    Then expected step navigation, editable fields, loading/blocked/toast and responsive layout
    And focus, editable state and loading/blocked toast remain accessible
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-RPT-005 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-RPT-005 - Unauthorized principal opens Generated artifact or storage linkage
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; private generated artifact owned by another scoped principal
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Unauthorized principal opens Generated artifact or storage linkage
    And perform the scenario action using an approved domain/service test client: Unauthorized principal opens Generated artifact or storage linkage
    And request detail and download directly without authorization
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-005
    Then permission-scope checks prevent disclosure even by direct URL
    And no file bytes, link/token or private metadata disclosure
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-RPT-006 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-RPT-006 - Schedule modified/deleted after run admitted
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; admitted scheduled run snapshot and editable source schedule
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Schedule modified/deleted after run admitted
    And perform the scenario action using an approved domain/service test client: Schedule modified/deleted after run admitted
    And change/delete schedule before worker reads accepted run
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-006
    Then run uses committed snapshot of accepted delivery intent, not mutable definition
    And run uses immutable original scope and delivery intent
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-RPT-007 @positive @medium @ui @specified @owner_review
  Scenario: UAT-RPT-007 - Browse Generated, Templates, Schedules and Storage registries
    Given reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup; Generated/Templates/Schedules/Storage registries with >5 rows
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Browse Generated, Templates, Schedules and Storage registries
    And perform the scenario action using an approved browser or domain test client: Browse Generated, Templates, Schedules and Storage registries
    And filter/page each registry, open detail and inspect download state
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-RPT-007
    Then scoped filters/pagination, detail handoff, evidence state, downloadable artifact metadata
    And scoped pagination and artifact readiness remain truthful
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

