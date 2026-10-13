# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Kubernetes — ConfigMaps, Secrets & Resource Operations
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KOP-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-KOP-001 - Permitted operator creates/edits ConfigMap in sandbox
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy
    When permitted operator creates/edits ConfigMap in sandbox
    Then provider read-back matches intended data; KAORI job/activity evidence accurate

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KOP-002 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-KOP-002 - ConfigMap submit/delete uses stale identity, missing rights or conflict
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy
    When configMap submit/delete uses stale identity, missing rights or conflict
    Then no unintended overwrite/delete; operator gets actionable feedback

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-KOP-003 @positive @medium @ui @draft @not_run
  Scenario: UAT-KOP-003 - Secret operation form loads and validates bounded metadata
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy
    When secret operation form loads and validates bounded metadata
    Then form labels, modal, loading, focus, feedback and layout follow shared standards

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Denied HTTP/permission assertion, sanitized browser trace, audit state and negative secret-leak assertions.
  # Isolation: Only non-sensitive known fixture Secret; redact every captured artifact.
  @UAT-KOP-004 @negative @high @ui @non_ui @detailed @not_run
  Scenario: UAT-KOP-004 - Secret reveal rejects user without approved policy
    Given synthetic Secret in disposable namespace
    And test user lacks reveal policy/approval. Do not use real secret values
    When visit permitted Kubernetes Administration/Secret Reveal surfaces as restricted user
    And attempt to open a protected reveal flow
    And also invoke direct reveal request where safe
    And inspect response, Activity, trace/log redaction and Secret state
    Then reveal is denied before any one-time disclosure occurs
    And secret value never appears in browser DOM, response, screenshot, trace or logs
    And no false approved/revealed audit is recorded

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KOP-005 @negative @high @non_ui @draft @not_run
  Scenario: UAT-KOP-005 - TLS Secret rotation encounters wrong target or partial provider failure
    Given dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy
    When tLS Secret rotation encounters wrong target or partial provider failure
    Then no false rotation success; pre/post identity and recovery evidence preserved

