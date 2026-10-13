# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Kubernetes — Cluster Registration & Provider Readiness
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KCL-001 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-KCL-001 - Permitted operator registers a valid cluster and validates connection
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved
    When permitted operator registers a valid cluster and validates connection
    Then correct cluster identity/readiness, committed configuration and audit evidence

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KCL-002 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-KCL-002 - Cluster credentials/endpoint/TLS trust are invalid
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved
    When cluster credentials/endpoint/TLS trust are invalid
    Then clear validation failure; no false Connected/Ready state or leaked credential

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KCL-003 @negative @high @non_ui @draft @not_run
  Scenario: UAT-KCL-003 - Provider is unavailable after committed cluster inventory exists
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved
    When provider is unavailable after committed cluster inventory exists
    Then read-only committed state remains truthful; live writes fail closed

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KCL-004 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-KCL-004 - Restricted user submits cluster configuration mutation
    Given disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved
    When restricted user submits cluster configuration mutation
    Then authorization denial and no external or committed mutation

