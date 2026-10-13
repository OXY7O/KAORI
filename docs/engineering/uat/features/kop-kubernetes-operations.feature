# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Kubernetes — ConfigMaps, Secrets & Resource Operations
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KOP-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KOP-001 - Permitted operator creates/edits ConfigMap in sandbox
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; disposable ConfigMap in approved sandbox Namespace
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Permitted operator creates/edits ConfigMap in sandbox
    And perform the scenario action using an approved browser or domain test client: Permitted operator creates/edits ConfigMap in sandbox
    And create/edit keys then read exact provider UID/resourceVersion
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-001
    Then provider read-back matches intended data; KAORI job/activity evidence accurate
    And provider content and job/Activity reflect the admitted mutation
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KOP-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KOP-002 - ConfigMap submit/delete uses stale identity, missing rights or conflict
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; stale ConfigMap version or restricted delete actor
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: ConfigMap submit/delete uses stale identity, missing rights or conflict
    And perform the scenario action using an approved browser or domain test client: ConfigMap submit/delete uses stale identity, missing rights or conflict
    And submit edit/delete against stale UID then reobserve provider
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-002
    Then no unintended overwrite/delete; operator gets actionable feedback
    And no overwrite/delete and actionable failure feedback
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-KOP-003 @positive @medium @ui @specified @owner_review
  Scenario: UAT-KOP-003 - Secret operation form loads and validates bounded metadata
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; safe Secret metadata fixture without real secret values
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Secret operation form loads and validates bounded metadata
    And perform the scenario action using an approved browser or domain test client: Secret operation form loads and validates bounded metadata
    And open form and submit invalid metadata on mobile
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-003
    Then form labels, modal, loading, focus, feedback and layout follow shared standards
    And accessible error, focus and modal do not leak secret contents
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: Denied HTTP/permission assertion, sanitized browser trace, audit state and negative secret-leak assertions.
  # Isolation: Only non-sensitive known fixture Secret; redact every captured artifact.
  @UAT-KOP-004 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-KOP-004 - Secret reveal rejects user without approved policy
    Given synthetic Secret in disposable namespace; test user lacks reveal policy/approval. Do not use real secret values
    And the actor permission, selected source and original state are recorded
    When visit permitted Kubernetes Administration/Secret Reveal surfaces as restricted user
    And attempt to open a protected reveal flow; also invoke direct reveal request where safe
    And inspect response, Activity, trace/log redaction and Secret state
    Then reveal is denied before any one-time disclosure occurs
    And secret value never appears in browser DOM, response, screenshot, trace or logs
    And no false approved/revealed audit is recorded

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KOP-005 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-KOP-005 - TLS Secret rotation encounters wrong target or partial provider failure
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy; disposable TLS Secret with wrong target or injected partial failure
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: TLS Secret rotation encounters wrong target or partial provider failure
    And perform the scenario action using an approved domain/service test client: TLS Secret rotation encounters wrong target or partial provider failure
    And attempt controlled rotation then compare fingerprint/version
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KOP-005
    Then no false rotation success; pre/post identity and recovery evidence preserved
    And no false rotation success; recovery and original identity remain visible
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

