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

  # Layer: UI; risk: Medium; #2605 Kubernetes Admin / #1738 QA specification.
  # Machine execution remains NOT RUN; bounded human acceptance is recorded on #2605.
  @UAT-LIF-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-LIF-004 - Kubernetes Admin Overview and Secret Reveal workspace navigation
    Given an authorized Kubernetes Admin operator and selected Kubernetes X300 cluster
    And the global Secret Reveal gate is deployment-managed and read-only in this workspace
    When the operator opens the Kubernetes Admin Overview
    And opens Secret Reveal, Cluster Prerequisites, then Namespace Policies
    And reloads a direct policies deep link
    Then canonical Hero, committed coverage and Secret Reveal configuration render
    And tab, selected cluster and policy-view context survive navigation and browser refresh
    And credential readiness and operator attestations remain readable without exposing Secret payloads
    And inline namespace policy editors remain collapsed until explicitly opened

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


  # Layer: ui; risk: medium; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-006 @positive @medium @ui @specified @owner_review
  Scenario: UAT-LIF-006 - Namespace Policy pagination, search and filters retain canonical state
    Given a selected cluster with 25 live namespaces and two enabled policies
    When the operator moves to page 2 then page 3 of the five-row Namespace Policies table
    And uses Previous to return to page 2 and refreshes the browser
    And searches for harbor, clears filters, and selects Enabled only
    And changes Rows Per Page from 5 to 10
    Then numbered pagination preserves its selected page across HTMX updates and reload
    And search and Enabled only scope the matching live namespace policies correctly
    And the header says 25 Total Namespaces while the footer counts current filter matches
    And ten-row pagination has three pages without opening policy editors

  # Layer: ui; risk: medium; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-007 @negative @medium @ui @specified @owner_review
  Scenario: UAT-LIF-007 - Cancel discards an unsaved namespace policy change
    Given the committed minio namespace policy is Step-up authentication
    When the operator opens Edit Policy for minio
    And changes the proposed policy to Disabled without clicking Save Policy
    And clicks Cancel and refreshes the page
    Then the inline editor closes with no committed change
    And the original Step-up authentication policy and enabled namespace count remain unchanged

  # Layer: ui + non_ui; risk: high; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-008 @positive @high @ui @@non_ui @specified @owner_review
  Scenario: UAT-LIF-008 - Approved Harbor policy save and rollback preserve audit correlation
    Given a permitted operator expressly authorizes a nonproduction harbor policy test
    And harbor is Available with a Disabled policy and no impacted pending reveal requests
    When the operator saves Approval required for harbor
    And confirms the new policy and committed Activity Audit evidence
    And immediately saves Disabled to restore the original policy
    Then the enabled namespace count rises from two to three and returns to two
    And the first audit event records disabled to approval_required
    And the second audit event records approval_required to disabled
    And both event keys and actor attribution remain correct without exposing Secret payloads

  # Layer: ui + non_ui; risk: high; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-009 @negative @high @ui @@non_ui @specified @owner_review
  Scenario: UAT-LIF-009 - Viewer direct requests cannot read Kubernetes Admin configuration
    Given a Viewer without Kubernetes Secret Reveal management permission
    When the Viewer requests the Kubernetes Admin Overview URL directly
    And requests the Secret Reveal workspace URL directly
    Then the server denies both unauthorized read requests
    And the KAORI Access Denied page explains the role and access administrator contact
    And no cluster credential or namespace policy data is disclosed
    And a permitted administrator can later read the unchanged configuration

  # Layer: non_ui; risk: high; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-010 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-LIF-010 - Unauthorized or missing-CSRF policy POST cannot commit changes
    Given isolated test identities and a known committed namespace policy
    When a Viewer attempts a direct namespace policy POST
    And a permitted test principal posts without a valid CSRF token
    Then the server rejects each unauthorized request
    And no policy update or successful Activity Audit event is committed
    And the original policy and Secret confidentiality are preserved

  # Layer: ui + non_ui; risk: high; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-011 @negative @high @ui @@non_ui @specified @owner_review
  Scenario: UAT-LIF-011 - Unavailable namespace source and unready clusters fail closed
    Given an isolated cluster with controllable Namespace provider availability and readiness
    When the Namespace provider cannot confirm live namespace presence
    And an operator attempts policy enablement on an unavailable namespace or unready cluster
    Then source Unknown is distinct from an authoritatively Missing namespace
    And the enablement attempt fails closed without pretending runtime access is verified
    And no Secret value or unauthorized policy change is exposed

  # Layer: ui; risk: medium; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-012 @positive @medium @ui @specified @owner_review
  Scenario: UAT-LIF-012 - Audit Warning presents successful namespace restriction as attention
    Given committed Activity Audit events for an approved harbor policy change and rollback
    When the auditor opens the Success policy enable event
    And opens the Warning policy disable event
    Then the Success record retains its before and after changes and event key
    And the Warning record shows Attention Summary and Review Guidance
    And no failure claim or retry instruction is displayed for a successful disable
    And a genuine Error event still presents Failure Summary and Next Review Step

  # Layer: ui; risk: medium; authority #2605/#2457/#1384 and catalog #1738.
  # Separate candidate-specific human evidence from unrun executable Gherkin scenarios.
  @UAT-LIF-013 @positive @medium @ui @specified @owner_review
  Scenario: UAT-LIF-013 - Kubernetes Admin responsive visual and keyboard coverage
    Given the approved KAORI Violet light and dark design system and six canonical viewports
    When the operator navigates workspace tabs, policy filters and inline editors by keyboard
    And inspects loading, blocked and no-results states across the supported viewports
    Then focus order and accessible control labels remain correct
    And no action, table or guidance is clipped in light or dark mode
    And visual baselines are not silently accepted or regenerated
