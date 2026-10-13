# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Artifact Registry — Inventory, Security, Runtime & Governance
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-REG-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-REG-001 - Operator inspects registry/artifact inventory and synchronized evidence
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; committed registry project/artifact/tag/digest generation
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator inspects registry/artifact inventory and synchronized evidence
    And perform the scenario action using an approved browser or domain test client: Operator inspects registry/artifact inventory and synchronized evidence
    And filter registry/project, open artifact digest detail
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-001
    Then correct registry/project/artifact/version identity, freshness and pagination
    And identity and freshness match authoritative synchronized evidence
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-REG-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-REG-002 - Security vulnerability scan is absent, failed or partial
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; missing, failed and partial vulnerability scan fixtures
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Security vulnerability scan is absent, failed or partial
    And perform the scenario action using an approved browser or domain test client: Security vulnerability scan is absent, failed or partial
    And open security posture and scan detail for each state
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-002
    Then unknown/partial posture not labeled Secure/Healthy
    And never label partial or unavailable scan Secure/Healthy
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Normalized binding assertion, source fingerprint, UI detail screenshot, trace and empty/degraded state.
  # Isolation: Read-only fixture; no registry image or cluster resource mutation.
  @UAT-REG-003 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-REG-003 - Stale artifact-to-runtime identity cannot claim verified binding
    Given two distinct registry/runtime identities or stale runtime snapshot fixture; no provider writes required
    And the actor permission, selected source and original state are recorded
    When record artifact registry identity and currently committed runtime binding evidence
    And make target cluster/runtime evidence stale, missing or identity-mismatched in fixture
    And open Runtime Usage/Topology details and inspect binding status
    And check underlying normalized correlation status against source fingerprint
    Then uI labels missing/unverified/stale binding truthfully, not verified/Ready
    And no false artifact-to-runtime link or cross-cluster association is committed
    And uI remains navigable and usable in error/unknown state at supported viewports

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-REG-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-REG-004 - User opens Runtime Usage topology/detail and applies scoped filters
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; runtime digest binding and two Kubernetes cluster snapshots
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: User opens Runtime Usage topology/detail and applies scoped filters
    And perform the scenario action using an approved browser or domain test client: User opens Runtime Usage topology/detail and applies scoped filters
    And filter Runtime Usage and inspect topology identity/modal
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-004
    Then links/tabs/modal and filter states work with canonical responsive layout
    And links preserve registry digest and workload UID/cluster
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-REG-005 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-REG-005 - Registry provider disabled or sync failed after earlier success
    Given registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved; historically Ready registry whose provider is now disabled/failed
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Registry provider disabled or sync failed after earlier success
    And perform the scenario action using an approved domain/service test client: Registry provider disabled or sync failed after earlier success
    And reload readiness and affected consumer after provider state change
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-REG-005
    Then latest committed source state truthfully supersedes old Ready evidence
    And historical Ready does not override current failed source
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

