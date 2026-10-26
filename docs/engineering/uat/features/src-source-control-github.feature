# KAORI UAT — Source Control / GitHub App acceptance specification
# Authority: #3371 (child workstream of #1738 / #1724), #3306, #559, #2740-#2742, #724.
# Convention: existing #1738 .feature specifications, #1725 and docs/TESTING.md.
# These scenarios are SPECIFIED / OWNER REVIEW. They have NOT been executed by scenario ID.
# No Cucumber runner is introduced; existing pytest/Playwright + Dev Container UAT own evidence.
# Do not use real provider mutation/deletion outside an authorized disposable sandbox.

Feature: Source Control — GitHub App connection, committed repository inventory and lifecycle
  GitHub owns repository grants and runtime facts; KAORI orchestrates jobs, normalizes
  committed evidence and governs instance identity, audit, scope and history.

  Background:
    Given the exact KAORI candidate SHA, installed app provider and authorized test scope are recorded
    And every identity, test resource and actor is isolated in the Dev Container or disposable GitHub sandbox
    And secret values, raw webhook bodies and access tokens are excluded from UAT artifacts

  # Layer: UI; risk: Medium; evidence: UI navigation, exact route and header screenshot.
  @UAT-SRC-001 @positive @medium @ui @specified @owner_review
  Scenario: UAT-SRC-001 - Capability-first provider and installation navigation
    Given an authorized local administrator with Source Control provider available and a registered installation
    When the administrator opens Integrations then Source Control then GitHub Connection Registry and selects an installation
    Then the GitHub provider workspace and canonical instance detail display the correct installation identity
    And the Configuration, Validation & Capabilities, Runtime & History, and Inventory & Lifecycle tabs navigate without changing provider authority

  # Layer: Both; risk: High; evidence: test response, DB before/after, sanitized network call ledger.
  @UAT-SRC-002 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-002 - Test Connection issues a bounded proof without registering
    Given a disposable GitHub App installation and correctly scoped credential input not yet registered
    When the administrator selects GitHub, completes the form and presses Test Connection
    Then GitHub App identity and installation ownership are verified for the supplied scope
    And no IntegrationInstance, SourceInstallation, grant or repository snapshot is committed by the test alone

  # Layer: Both; risk: High; evidence: toast screenshot, canonical ID, sanitized audit record and DB read-back.
  @UAT-SRC-003 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-003 - Register the tested connection and retain pending readiness
    Given a valid, unexpired Test Connection proof for the exact same GitHub App inputs
    When the administrator registers the verified installation and opens Connection Registry
    Then a single canonical Source Control GitHub connection is persisted and the success toast is displayed
    And the connection is Validation Required until separately admitted Full Validation, with repository inventory still unobserved

  # Layer: Both; risk: High; evidence: HTTP errors, unchanged DB, denied provider request and redacted logs.
  @UAT-SRC-004 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-004 - Reject invalid credentials and mismatched proof
    Given invalid PEM, incorrect App or Installation ID, or altered form inputs after Test Connection
    When the administrator attempts Test Connection or submits registration using an incompatible proof
    Then registration is rejected without creating a canonical connection or claiming readiness
    And raw private keys, webhook secrets and provider tokens never appear in HTML, audit, logs or trace artifacts

  # Layer: Both; risk: Medium; evidence: before/after canonical rows, existing grant/ref history, toast and audit.
  @UAT-SRC-005 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-005 - Update descriptive configuration without erasing identity or evidence
    Given a registered validated GitHub connection with committed repository and job history
    When the administrator edits the connection name or description and saves with unchanged App identity
    Then the same canonical instance and installation IDs are preserved
    And existing committed grants, revisions, and job history remain linked to the connection without fabricated synchronization

  # Layer: Both; risk: High; evidence: controlled App fixture, impacted installation set, persisted readiness and audit.
  @UAT-SRC-006 @positive @high @non_ui @ui @specified @owner_review
  Scenario: UAT-SRC-006 - Rotate shared App credentials and invalidate affected validations
    Given two disposable installations referencing the same encrypted GitHub App credential
    When the administrator verifies a replacement credential and saves the approved rotation
    Then the shared encrypted credential changes only after successful verification
    And every affected installation requires Full Validation again and raw secrets remain inaccessible

  # Layer: Both; risk: High; evidence: old/new installation and canonical IDs, replacement audit, grants and jobs.
  @UAT-SRC-007 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-007 - Register a verified successor without reparenting predecessor evidence
    Given an existing GitHub installation and a verified successor registration scope
    When the administrator performs the explicit installation replacement flow
    Then a distinct successor canonical identity is created and requires its own validation
    And the predecessor's committed grants, exact revisions, JobExecution and audit remain associated with the predecessor

  # Layer: Both; risk: High; evidence: JobExecution ID/status, permission matrix, provider API evidence and committed readiness.
  @UAT-SRC-008 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-008 - Full Validation verifies only provider permissions and readiness
    Given a registered active GitHub installation with provider access and required read permissions
    When the administrator runs Full Validation and waits for its authorized job result
    Then the capability matrix identifies verified read permissions and the connection's validation readiness reflects committed proof
    And the completed validation alone does not create repository inventory, latest SHA or runtime health

  # Layer: Both; risk: High; evidence: permission failure fixture, stored job status, UI warning and unchanged grants.
  @UAT-SRC-009 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-009 - Missing permissions and failed validation cannot become Ready
    Given a GitHub App lacking a required read permission or whose credentials have expired
    When the administrator submits Full Validation and inspects the resulting capability gap
    Then readiness is blocked or requires correction with a clear next action
    And previous committed repository evidence remains historical and is not rewritten as a successful new collection

  # Layer: Both; risk: High; evidence: Runtime Refresh JobExecution, last checked timestamps and runtime decision.
  @UAT-SRC-010 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-010 - Runtime Refresh uses independent committed health evidence
    Given a valid installation whose Full Validation result is already known
    When the administrator starts Runtime Refresh and inspects Runtime Health & Diagnostics after the worker completes
    Then runtime health is based on the admitted runtime job and its committed observation
    And Full Validation or connection registration alone never renders Runtime Health as Healthy

  # Layer: Both; risk: Medium; evidence: five-row and multi-page screenshots, filter URLs, scoped JobExecution query.
  @UAT-SRC-011 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-011 - Recent Jobs filters and paginates committed job outcomes
    Given at least six committed jobs from more than one queue or status for the selected installation
    When the administrator searches operation or Job ID and changes Queue, Job Status, Rows, and page
    Then search and filter results update automatically over all scoped jobs with the standard default five rows
    And operation, Job ID, readable UTC creation time, queue and semantic result indicator remain visible without Apply Filters

  # Layer: Both; risk: Medium; evidence: signed receipt fixture, empty-state screenshot, event/state filter query.
  @UAT-SRC-012 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-012 - Signed webhook receipts remain distinct transport evidence
    Given an authorized GitHub installation with either zero or several committed signed webhook receipts
    When the administrator opens Signed Webhook Deliveries and changes Search Event, Event Type and Processing State
    Then the table filters only this installation's received receipts and keeps Rows and pagination independent of Recent Jobs
    And zero signed receipts never establishes missing repository access or successful synchronization

  # Layer: Non-UI; risk: High; evidence: HTTP status, trusted digest/dedup fixture, denied work and sanitized audit.
  @UAT-SRC-013 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-SRC-013 - Reject unsigned, invalid, replay-conflicting or foreign webhooks
    Given a sandbox webhook ingress explicitly enabled with a known App secret and two different installation IDs
    When an attacker submits invalid signatures, mismatched installation identity, or a reused delivery ID with conflicting body
    Then the request is rejected before unauthorized downstream collection
    And no raw webhook body, short-lived token, cross-installation receipt or unauthorized job is committed

  # Layer: Both; risk: High; evidence: queued JobExecution, toast screenshot, audit, before/after committed generation.
  @UAT-SRC-014 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-014 - Sync Repositories queues worker work with a transient toast
    Given a Full Validation-ready active GitHub installation and an eligible repository sync worker
    When the administrator presses Sync Repositories on Inventory & Lifecycle
    Then Repository Sync Queued appears as a KAORI operational toast and no permanent blue Connection Operation block appears
    And only successful worker publication changes committed grants; queue admission is not described as completed sync

  # Layer: Both; risk: High; evidence: warning toast, rejected job admission and unchanged committed generation.
  @UAT-SRC-015 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-015 - Sync is blocked before readiness, denied worker, or invalid scope
    Given an unvalidated, retired, or otherwise ineligible installation with previously committed evidence
    When the administrator attempts a repository sync through the permitted UI or its direct POST endpoint
    Then the request is disabled or rejected with Repository Sync Blocked feedback as applicable
    And no new successful grant generation or synthesized current repository inventory is produced

  # Layer: Both; risk: High; evidence: installation-scoped DB join, full exact revision tooltip, observed UTC screenshot.
  @UAT-SRC-016 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-016 - Registry displays only committed granted repositories and exact SHA
    Given a completed authorized installation collection with a known repository, default branch and observed exact revision
    When the administrator opens Committed Repository Registry
    Then the table shows repository, access status, default branch, source-qualified exact SHA and observation time
    And the unfiltered Committed Grants metric and the table's filtered match count remain independent

  # Layer: Both; risk: High; evidence: three fixture states, visible empty states, count and DB read-back.
  @UAT-SRC-017 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-017 - Unobserved inventory is not zero and filtered zero is not lost grants
    Given one installation without committed collection, another with a proven empty collection, and one with grants but no matching filters
    When the administrator opens each Inventory & Lifecycle view and applies a filter with no matching rows
    Then the UI distinguishes Not Observed, confirmed zero repositories, and No Matching Repositories
    And an active filter never overwrites the unfiltered committed grant total or fabricates missing provider evidence

  # Layer: Both; risk: Medium; evidence: matching totals, literal search request, HTML, Rows and page URLs.
  @UAT-SRC-018 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-018 - Repository filters run server-side before canonical pagination
    Given more than five committed authorized repositories covering public/private, active/archived states
    When the administrator searches repository name or native ID and varies Visibility, Repository State, Rows and numeric page
    Then the search is case-insensitive and literal with bounded length, and all filters apply before the five-row default paginator
    And Clear Filters restores the current installation scope and keeps the selected page-size option

  # Layer: Non-UI; risk: High; evidence: provider pagination ledger, selection scope, committed generation and grants.
  @UAT-SRC-019 @positive @high @non_ui @specified @owner_review
  Scenario: UAT-SRC-019 - Selected and all-grant collection respect exhaustive provider scope
    Given two disposable GitHub App installations with independently verified Selected and All repository grants
    When the admitted collector enumerates bounded pages and publishes a fully verified generation
    Then the recorded coverage and effective-dated grant set match only the authorized installation scope
    And incomplete, failed or foreign-owner pagination never establishes absence or expands selected grants

  # Layer: Non-UI; risk: High; evidence: concurrent generation IDs, worker result, unchanged prior rows and evidence.
  @UAT-SRC-020 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-SRC-020 - Stale generation and provider failure preserve committed history
    Given a previously committed successful collection and two overlapping or failed collection attempts
    When the slower stale generation completes after a newer admitted generation or the provider becomes unavailable
    Then stale or failed publication cannot replace the latest proven committed collection
    And the previous grants, references and exact SHA history are retained without a false zero or deletion

  # Layer: Non-UI; risk: High; evidence: stable native ID, before/after name, archive and effective-dated grant transitions.
  @UAT-SRC-021 @positive @high @non_ui @specified @owner_review
  Scenario: UAT-SRC-021 - Rename, archive and access loss preserve native repository identity
    Given a repository whose owner/name is renamed, archived, or removed from one App installation's grants
    When the collector observes the change in an exhaustive authorized generation
    Then native repository ID and revision/reference evidence remain correlated across rename or archive
    And loss of one installation's access is distinguished from repository deletion for other installations

  # Layer: UI; risk: Medium; evidence: modal screenshot, Cancel/Escape trace, unchanged identity and activity read-back.
  @UAT-SRC-022 @positive @medium @ui @specified @owner_review
  Scenario: UAT-SRC-022 - Cancel Delete Connection without a state mutation
    Given an active or disabled-but-not-retired GitHub connection and a privileged administrator
    When the administrator opens Delete Connection and dismisses the modal with Cancel or Escape
    Then the modal closes with keyboard focus safely restored
    And canonical enabled/lifecycle, grants, bindings, jobs and provider permissions remain unchanged

  # Layer: Both; risk: High; evidence: job status and guard count, warning toast, unchanged canonical and binding records.
  @UAT-SRC-023 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-023 - Prevent connection deletion while a related job is active
    Given an active GitHub connection with an admitted queued or running canonical JobExecution
    When the administrator confirms Delete Connection using a valid CSRF token
    Then the existing deletion guard rejects retirement with a warning toast
    And the connection stays available in the active registry and all committed evidence remains intact

  # Layer: Both; risk: High; evidence: canonical lifecycle, disabled bindings, active registry and historical records, GitHub read-back.
  @UAT-SRC-024 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-024 - Retire a connection without revoking GitHub or deleting evidence
    Given an active or disabled GitHub connection with no pending KAORI jobs and a disposable provider test scope
    When the administrator confirms Delete Connection using the scoped confirmation dialog
    Then the connection becomes disabled and retired and disappears from the active registry
    And committed grants, exact revisions, JobExecution, signed receipts and audit persist and GitHub permissions are not revoked

  # Layer: Both; risk: High; evidence: 403/404/400 evidence, unchanged DB, no provider call and sanitized log.
  @UAT-SRC-025 @negative @high @non_ui @ui @specified @owner_review
  Scenario: UAT-SRC-025 - Reject unauthorized reads, POSTs and CSRF bypass
    Given a non-admin actor, an unauthorized installation identity, and a request lacking valid CSRF
    When the actor requests protected installation detail, table fragments, validation, sync or delete directly
    Then resource and management checks reject out-of-scope access before exposing private data or mutating state
    And an invalid or absent CSRF token never queues a job or retires a connection

  # Layer: Both; risk: High; evidence: authorized query predicates, UI/API snapshots, native ID scope and role evidence.
  @UAT-SRC-026 @negative @high @non_ui @ui @specified @owner_review
  Scenario: UAT-SRC-026 - Do not leak data between two independent GitHub installations
    Given two disposable installations with disjoint grants, jobs, receipts and revision observations
    When the administrator views one installation then switches the requested installation ID or filter query
    Then all evidence readbacks are scoped to the installation explicitly authorized for the request
    And no foreign repository, job, webhook receipt, secret or upstream App grant is silently combined

  # Layer: UI; risk: Medium; evidence: desktop/mobile screenshots, keyboard trace, theme, URL and focus state.
  @UAT-SRC-027 @positive @medium @ui @specified @owner_review
  Scenario: UAT-SRC-027 - Maintain shared Violet accessible tab and table interactions
    Given the GitHub connection detail is loaded in both approved light and dark themes and supported viewports
    When the administrator changes tabs, opens title-level Guide, filters tables and navigates Back/Forward with keyboard and pointer
    Then Framed Workspace Tabs, shared cards, loaders, toast, Guide and tables remain aligned without unintended horizontal clipping
    And focus, labels, selected tab, accessible dialogs and user-visible error/empty states remain operable

  # Layer: Both; risk: Medium; evidence: no-JS browser run, exact URL filter values, table and pagination read-back.
  @UAT-SRC-028 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-SRC-028 - Provide normal GET fallback when HTMX or JavaScript is unavailable
    Given a GitHub installation has committed multiple repository and job rows and JavaScript is disabled
    When the administrator submits registry filters and moves through pagination using normal links
    Then the same authorized server-filtered results and default five-row page size are returned
    And no extra visible Apply Filters control appears when JavaScript is enabled

  # Layer: Non-UI; risk: High; evidence: logs, JobExecution, rendered HTML, persisted tables and network capture review.
  @UAT-SRC-029 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-SRC-029 - Prevent raw credentials and provider content from leaking into KAORI evidence
    Given GitHub App PEM, webhook secret and short-lived installation tokens are present only in permitted encrypted and in-memory flows
    When the administrator tests, registers, rotates, validates, refreshes and synchronizes using disposable fixtures
    Then no raw credential, webhook body, full Git clone, repository file content or token is retained in operational evidence
    And only bounded authorized metadata, exact source identity and sanitized audit are committed

