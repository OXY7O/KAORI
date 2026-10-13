# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Kubernetes — Governance & TLS
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-GOV-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-GOV-001 - Operator reviews TLS certificate inventory and governance finding
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; known TLS cert SAN, issuer, expiration and committed source
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator reviews TLS certificate inventory and governance finding
    And perform the scenario action using an approved browser or domain test client: Operator reviews TLS certificate inventory and governance finding
    And open Governance certificate finding and authoritative detail
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-001
    Then certificate identity, expiry/source and readiness reflect authoritative evidence
    And certificate fields and readiness match committed certificate identity
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-GOV-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-GOV-002 - TLS rotation preflight fails (identity/permission/impact)
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; disposable TLS Secret and deliberately failed preflight
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: TLS rotation preflight fails (identity/permission/impact)
    And perform the scenario action using an approved browser or domain test client: TLS rotation preflight fails (identity/permission/impact)
    And record fingerprint/UID, attempt rotation and reobserve provider
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-002
    Then change is blocked; original Secret/cert remains unchanged
    And no cert replacement or success claim after failure
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-GOV-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-GOV-003 - Capacity/quota or policy evidence is expired or conflicting
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; expired capacity policy snapshot and positive quota request
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Capacity/quota or policy evidence is expired or conflicting
    And perform the scenario action using an approved domain/service test client: Capacity/quota or policy evidence is expired or conflicting
    And submit guarded quota change and reread decision and provider
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-003
    Then mutation admission fails closed; no optimistic capacity claims
    And fail-closed admission preserves quota and avoids optimistic capacity
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-GOV-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-GOV-004 - Operator moves from governance finding to source evidence
    Given safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox; finding with linked evidence and another with missing source
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator moves from governance finding to source evidence
    And perform the scenario action using an approved browser or domain test client: Operator moves from governance finding to source evidence
    And follow both finding links and inspect accessible blocked state
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-GOV-004
    Then scoped navigation, accessible details and consistent blocked/error states
    And valid link remains scoped and missing source never jumps to another asset
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

