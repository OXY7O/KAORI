# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Integrations — Registry, Provider Configuration & Runtime
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-ING-001 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-ING-001 - Operator registers an allowed provider instance and validates it
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; allowed capability, provider and disposable instance endpoint
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator registers an allowed provider instance and validates it
    And perform the scenario action using an approved browser or domain test client: Operator registers an allowed provider instance and validates it
    And register instance then validate and reopen its detail
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-001
    Then capability-first domain/instance identity, sanitized connection readiness and audit
    And capability-first identity and sanitized readiness match provider
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Original first-wave procedure — verify against current candidate.
  # Evidence: UI modal/validation trace, provider result, committed instance state, consumer posture and safe audit.
  # Isolation: Use deliberate invalid sandbox configuration; preserve existing live integration instance configuration.
  @UAT-ING-002 @negative @high @ui @non_ui @specified @first_wave
  Scenario: UAT-ING-002 - Invalid provider credentials/TLS do not produce Ready state
    Given isolated Metrics Source, Alertmanager or Object Storage provider test instance with deliberately invalid validation inputs
    And the actor permission, selected source and original state are recorded
    When open the existing capability-first Integrations instance/configuration form
    And fill a non-secret invalid endpoint/certificate or disposable invalid credentials
    And trigger the owning provider validation and inspect operational UI feedback
    And inspect committed readiness/evidence and bound consuming views
    Then provider validation is rejected or degraded, never marked Ready
    And no fallback to another instance or cross-scope/source substitution
    And no sensitive validation payload in UI/audit/traces

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-ING-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-ING-003 - Disabled or stale provider still has previously committed metrics
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; disabled provider with old successful committed metrics
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Disabled or stale provider still has previously committed metrics
    And perform the scenario action using an approved domain/service test client: Disabled or stale provider still has previously committed metrics
    And inspect current consumer readiness after provider disable
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-003
    Then consumers cannot represent it as active/Ready or silently substitute data
    And old metrics remain historical; no active source substitution
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-ING-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-ING-004 - Navigate Integrations Overview → capability → instance detail and actions
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; two instance statuses under one capability
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Navigate Integrations Overview → capability → instance detail and actions
    And perform the scenario action using an approved browser or domain test client: Navigate Integrations Overview → capability → instance detail and actions
    And navigate Overview/capability/instance and trigger validate/modal
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-004
    Then tabs, validation states, badge, modal and HTMX fit Violet standard
    And correct breadcrumbs, HTMX and responsive Violet error state
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-ING-005 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-ING-005 - Metrics/Alertmanager or Source Binding points to wrong cluster/instance
    Given provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets; cross-cluster Metrics/Alertmanager binding mismatch
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Metrics/Alertmanager or Source Binding points to wrong cluster/instance
    And perform the scenario action using an approved domain/service test client: Metrics/Alertmanager or Source Binding points to wrong cluster/instance
    And attempt binding foreign provider then inspect consumer correlation
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-ING-005
    Then reject cross-scope binding rather than fallback to default or another source
    And no default provider fallback or foreign source admission
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

