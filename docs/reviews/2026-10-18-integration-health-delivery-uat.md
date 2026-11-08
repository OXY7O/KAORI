# Integrations — Health Degradation Outbound Delivery UAT

**Authority:** #2347 under #2331. **Admission:** review-only `kaori/review/staging-uat`; official CI/CD HOLD.

**Source of truth:** `IntegrationRuntimeObservation` committed by the existing provider-neutral runtime collector, not request-time polling or a UI validation toast. After a canonical instance's previous observation is **healthy** and its next persisted observation is **degraded/unhealthy**, the source enqueues one independent notification task. That task reloads the exact observation, denies inactive/disabled/foreign canonical instances, rejects observations superseded by a newer one, verifies healthy→degraded transition again, then emits `integrations.health_degraded` using the existing durable delivery journal.

This is a **health observation**, not a claim that an external provider outage is proven. No raw diagnostics, token, password or transport secret is transmitted. Only channels explicitly allowing Integrations and this event qualify. Broker unavailable after a committed observation can leave a missed outbound notification; that does **not** roll back the provider evidence or mean delivery succeeded.

```gherkin
Feature: Integrations health transition to a governed Notification Channel

  Background:
    Given a nonproduction provider is registered with a canonical IntegrationInstance
    And its runtime observation worker is configured
    And an enabled validated Notification Channel is scoped to Integrations health degradation

  @NINT-01 @positive
  Scenario: Healthy to unhealthy transition dispatches one correlated event
    Given the last committed IntegrationRuntimeObservation was healthy
    When the next observation for the same canonical provider becomes unhealthy
    Then the committed row is eligible for an asynchronous notification task
    And a qualifying channel receives event "integrations.health_degraded"
    And the event key identifies the exact committed observation

  @NINT-02 @negative
  Scenario: Repeated unhealthy polls do not generate alert storms
    Given a provider already has a degraded or unhealthy observation
    When another degraded or unhealthy observation is committed
    Then no new health transition notification task is queued

  @NINT-03 @negative
  Scenario: First observation is not a fabricated deterioration
    Given no prior observation exists for the integration
    When a nonhealthy observation is committed
    Then no health-degradation transition is claimed

  @NINT-04 @negative
  Scenario: Disabled or retired canonical instance cannot deliver
    Given the integration becomes disabled, retired or is deleted
    When the queued notification worker examines an old observation
    Then delivery is skipped

  @NINT-05 @negative
  Scenario: Superseded degradation cannot be delivered out of order
    Given a newer runtime observation exists for the integration
    When an older degradation notification task is executed
    Then it is skipped with stale_transition
    And no stale provider-state claim is delivered

  @NINT-06 @security
  Scenario: Provider diagnostics and credentials are never transported
    Given the observation contains sensitive diagnostics and raw error details
    When a notification message is built
    Then only safe integration identity, provider name and health state are included
    And no credentials or raw error diagnostics appear in payload or message

  @NINT-07 @resilience
  Scenario: Queue outage cannot roll back provider evidence
    Given a committed unhealthy transition exists
    When broker enqueue is unavailable
    Then the runtime observation remains committed
    And enqueue failure is reported separately without provider-delivery PASS

  @NINT-08 @visual
  Scenario: Integrations delivery choice is accessible
    When the Notification Channel modal is viewed in desktop/mobile light/dark mode
    Then Integrations is selectable with "Provider Health Degraded only"
    And its event label and form validation follow existing Violet patterns
```

Execution outcomes: **NINT-01..08 NOT RUN**. Evidence must include source previous/current observation IDs/timestamps, exact work and aggregation SHAs, instance active state, channel Test Delivery, event key, `NotificationDelivery` attempt and provider outcome, redacted logs, Visual QA screenshots and human acceptance. Run existing focused unit/contracts, Ruff, djLint and Celery topology verifier; no production mutations and no official admission/deployment.
