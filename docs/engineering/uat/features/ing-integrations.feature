# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# Reusable specification only: runtime outcomes and human decisions live in execution records.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Integrations — Registry, Provider Configuration & Runtime
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-ING-001 @positive @high @ui @non_ui @draft
  Scenario: UAT-ING-001 - Operator registers an allowed provider instance and validates it
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets
    When operator registers an allowed provider instance and validates it
    Then capability-first domain/instance identity, sanitized connection readiness and audit

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: UI modal/validation trace, provider result, committed instance state, consumer posture and safe audit.
  # Isolation: Use deliberate invalid sandbox configuration; preserve existing live integration instance configuration.
  @UAT-ING-002 @negative @high @ui @non_ui @detailed
  Scenario: UAT-ING-002 - Invalid provider credentials/TLS do not produce Ready state
    Given isolated Metrics Source, Alertmanager or Object Storage provider test instance with deliberately invalid validation inputs
    When open the existing capability-first Integrations instance/configuration form
    And fill a non-secret invalid endpoint/certificate or disposable invalid credentials
    And trigger the owning provider validation and inspect operational UI feedback
    And inspect committed readiness/evidence and bound consuming views
    Then provider validation is rejected or degraded, never marked Ready
    And no fallback to another instance or cross-scope/source substitution
    And no sensitive validation payload in UI/audit/traces

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-ING-003 @negative @high @non_ui @draft
  Scenario: UAT-ING-003 - Disabled or stale provider still has previously committed metrics
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets
    When disabled or stale provider still has previously committed metrics
    Then consumers cannot represent it as active/Ready or silently substitute data

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-ING-004 @positive @medium @ui @draft
  Scenario: UAT-ING-004 - Navigate Integrations Overview → capability → instance detail and actions
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets
    When navigate Integrations Overview → capability → instance detail and actions
    Then tabs, validation states, badge, modal and HTMX fit Violet standard

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-ING-005 @negative @high @non_ui @draft
  Scenario: UAT-ING-005 - Metrics/Alertmanager or Source Binding points to wrong cluster/instance
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets
    When metrics/Alertmanager or Source Binding points to wrong cluster/instance
    Then reject cross-scope binding rather than fallback to default or another source

