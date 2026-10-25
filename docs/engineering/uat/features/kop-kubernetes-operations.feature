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
  Scenario: UAT-KOP-001 - Permitted operator executes controlled ConfigMap CRUD in sandbox
    Given a dedicated disposable Kubernetes namespace and unique ConfigMap name
    And the operator has permission for create, update, and delete
    And the selected registered cluster, actor and initial state are recorded
    When the operator defines a key and runs Kubernetes server-side dry-run
    Then Create is enabled only for the latest validated form state
    And changing the form invalidates the prior validation
    When the operator creates the ConfigMap
    Then the Kubernetes API returns the new object with UID and resourceVersion
    And Activity Audit records kubernetes_configmap_created without field values
    When the operator selects the same live ConfigMap for Merge Selected Keys
    And reviews an effective diff and validates the latest intended changes
    Then the server-side dry-run succeeds and stale edits require revalidation
    When the operator applies the validated update
    Then Kubernetes preserves UID and advances resourceVersion
    And Activity Audit records kubernetes_configmap_updated without field values
    When the operator selects the exact ConfigMap for deletion
    And types the exact-name confirmation
    And performs deletion validation without issuing a DELETE request
    Then the server issues a signed ten-minute receipt bound to actor, target and resourceVersion
    When the operator explicitly confirms the destructive modal using the receipt
    Then the Kubernetes API returns NotFound for the exact target
    And Activity Audit records kubernetes_configmap_deleted without field values
    And no resources outside the disposable namespace were modified

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

  # Layer: Both; risk: High; QA extension under #3123 — capability-owner review required.
  # Evidence: authorized sandbox operator, screenshots/Activity Audit and Kubernetes tls.crt fingerprint, UID and resourceVersion read-back; no private key disclosure.
  # Isolation: Disposable namespace, self-signed matching pair and declared Ingress host; sync committed KAORI evidence, restore/delete fixtures after review.
  @UAT-KOP-006 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KOP-006 - Authorized single TLS Secret rotation changes only validated target
    Given an authorized TLS rotate operator selected a committed TLS Secret with complete Ingress host coverage
    And the disposable Secret UID, resourceVersion, certificate fingerprint and selected source SHA were recorded
    And a matching replacement certificate and private key cover the declared Ingress host
    When the operator uploads the pair and selects Validate Rotation
    Then the preview shows the intended host covered and Update TLS Secret is enabled
    When the operator applies the controlled rotation
    Then Kubernetes returns the same Secret UID and an advanced resourceVersion for the exact selected target
    And Kubernetes tls.crt read-back fingerprint matches the replacement certificate
    And a new TLS governance sync records the resulting certificate and audit outcome
    And no Secret key material appears in the evidence or activity records

  # Layer: Both; risk: High; QA extension under #3123 — capability-owner review required.
  # Evidence: negative browser validation, disabled apply control, unchanged provider fingerprints/UIDs and safe audit outcome.
  # Isolation: Use mismatched disposable test pairs or a certificate with a SAN unrelated to the declared test Ingress host.
  @UAT-KOP-007 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KOP-007 - Single TLS rotation rejects mismatched private key and uncovered SAN
    Given a committed disposable TLS Secret has confirmed Ingress host mapping and baseline fingerprint
    And the authorized operator opens its single TLS rotation workspace
    When the operator validates a certificate with a private key from another test pair
    Then the validation reports pair mismatch and keeps Update TLS Secret disabled
    When the operator validates a matching pair whose SAN omits the mapped Ingress host
    Then the preview reports uncovered host coverage and keeps Update TLS Secret disabled
    And the Kubernetes Secret fingerprint, UID and resourceVersion remain unchanged
    And neither rejected validation records a successful rotation or leaks uploaded private-key content

  # Layer: Both; risk: High; QA extension under #3123 — capability-owner review required.
  # Evidence: 2-target validation screenshot, native confirmation, per-target audit/result, fingerprints and Secret UID/resourceVersion; real bulk apply requires separate execution.
  # Isolation: Two explicitly checked disposable TLS Secrets with confirmed hosts covered by one replacement pair, and a separate unselected control Secret if available.
  @UAT-KOP-008 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KOP-008 - Authorized bulk TLS rotation updates exactly two validated Secrets
    Given the authorized bulk operator has selected two committed disposable TLS Secrets
    And each target has fresh Secret identity evidence and confirmed Ingress mapping
    And the uploaded replacement certificate and private key cover the hosts of both targets
    When the operator clicks Validate Selected
    Then validation reports two ready targets and enables Update Selected
    When the operator opens the canonical TLS confirmation dialog
    Then the dialog lists the two selected Secret names and the exact tls.crt and tls.key replacement consequence
    When the operator explicitly confirms Apply TLS Rotation
    Then the existing server-side preflight checks each target before its Kubernetes mutation
    And the result distinguishes successful, failed and persistence-warning targets without a false all-success claim
    And read-back for each successful target preserves its UID and matches the replacement certificate fingerprint
    And no unselected Secret is changed and Activity Audit contains no certificate or private-key payload

  # Layer: UI; risk: Medium; QA extension under #3123 — capability-owner review required.
  # Evidence: desktop/mobile screenshots, keyboard focus, no-PATCH browser trace, disabled/enabled state assertions and existing presentation-contract pytest.
  # Isolation: Valid disposable pair and targets; Cancel/Escape/backdrop are non-mutating, while any real apply is tested separately in sandbox.
  @UAT-KOP-009 @negative @medium @ui @specified @owner_review
  Scenario: UAT-KOP-009 - Bulk TLS confirmation and validation invalidation prevent accidental apply
    Given two disposable TLS Secrets have passed current bulk certificate validation
    When the operator opens the native confirmation dialog at the desktop viewport
    Then the selected target names and replacement impact are readable in KAORI Violet light and dark appearance
    And the three concise explanation lines remain compact on desktop and may wrap without overflow on mobile
    When the operator closes the dialog using Cancel, close icon, Escape or backdrop
    Then no Kubernetes mutation occurs and focus returns to the Update Selected launcher
    When the operator changes either uploaded file or a selected target after validation
    Then the main and modal apply actions remain disabled until a new successful validation
    And a stale validation state cannot submit a rotation through the browser
