# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Kubernetes — Cluster Registration & Provider Readiness
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KCL-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KCL-001 - Permitted operator registers a valid cluster and validates connection
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; disposable authorized Kubernetes endpoint
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Permitted operator registers a valid cluster and validates connection
    And perform the scenario action using an approved browser or domain test client: Permitted operator registers a valid cluster and validates connection
    And register exact endpoint, validate, then reread cluster configuration
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-001
    Then correct cluster identity/readiness, committed configuration and audit evidence
    And committed readiness and provider cluster identity are the same
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KCL-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KCL-002 - Cluster credentials/endpoint/TLS trust are invalid
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; invalid Kubernetes CA, credentials or endpoint fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Cluster credentials/endpoint/TLS trust are invalid
    And perform the scenario action using an approved browser or domain test client: Cluster credentials/endpoint/TLS trust are invalid
    And validate each invalid setting and reload cluster detail
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-002
    Then clear validation failure; no false Connected/Ready state or leaked credential
    And no false Connected badge and no credential disclosed in response
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KCL-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-KCL-003 - Provider is unavailable after committed cluster inventory exists
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; previous committed cluster snapshot and newly unreachable API
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Provider is unavailable after committed cluster inventory exists
    And perform the scenario action using an approved domain/service test client: Provider is unavailable after committed cluster inventory exists
    And open inventory then attempt provider-dependent write during outage
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-003
    Then read-only committed state remains truthful; live writes fail closed
    And snapshot remains provenance-labeled and the write is rejected
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KCL-004 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KCL-004 - Restricted user submits cluster configuration mutation
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved; restricted identity and committed Cluster baseline
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Restricted user submits cluster configuration mutation
    And perform the scenario action using an approved browser or domain test client: Restricted user submits cluster configuration mutation
    And issue direct cluster-mutation POST then reload connection identity
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KCL-004
    Then authorization denial and no external or committed mutation
    And rBAC denial preserves endpoint and credential references
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

