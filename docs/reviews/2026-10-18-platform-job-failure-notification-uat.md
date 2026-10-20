# Platform Operations — JobExecution Failed Delivery UAT

**Authority:** #2346 / #2331 / #1220. Review-only work branch, candidate for `kaori/review/staging-uat`. **Official admission HOLD.**

Committed `JobExecution` is the only business-state authority. A transition to terminal `failed` triggers an asynchronous maintenance task *after* the canonical job transaction commits. The worker reloads the row and only emits `NotificationEvent(domain='platform_operations', event_type='jobs.execution_failed')` for current failed records. One event key per public job identity is dispatched via existing validated channels and durable `NotificationDelivery`, without copying error messages, job parameters, provider credentials, or Activity Audit evidence. Automatic failure enqueue is best-effort; if Redis is unavailable the canonical failure remains committed but outbound delivery requires recovery. This is not an exactly-once delivery guarantee.

```gherkin
Feature: Governed job failure outbound delivery

  Background:
    Given a dedicated UAT job and a validated Platform Operations Notification Channel exist
    And official staging/deployment remain on hold

  @NJOB-01
  Scenario: Committed failed job triggers one governed outbound event
    Given a canonical JobExecution transitions from running to failed
    When its terminal transaction is committed
    Then a maintenance queue task reloads the persisted job
    And a channel matching Platform Operations and Failed Jobs can receive the event
    And NotificationDelivery has the stable public job identity

  @NJOB-02 @negative
  Scenario: Nonfailed or missing job is not emitted
    Given a queued, succeeded or missing JobExecution
    When the notification worker executes with that identity
    Then no outbound message is emitted

  @NJOB-03 @security
  Scenario: Sensitive worker errors cannot leak through outbound notifications
    Given the source job contains a secret-like exception message and job parameters
    When notification content is constructed
    Then only safe job type, public identity and status appear
    And no raw exception, arguments or credential payload appears

  @NJOB-04 @negative
  Scenario: No matching validated channel means no provider send
    Given a channel is disabled, unvalidated or configured for another domain
    When a failed job is emitted
    Then channel matching refuses the delivery

  @NJOB-05 @resilience
  Scenario: Broker failure never rolls back the canonical terminal job
    Given the maintenance queue cannot accept an enqueue
    When JobExecution terminal failure is committed
    Then the job remains failed
    And enqueue unavailability is recorded separately without claiming delivery
    And the operator can investigate missed outbound messages

  @NJOB-06 @regression
  Scenario: Duplicate failure dispatch does not send twice
    Given a delivery for a failed JobExecution already exists for the channel
    When the same notification task is replayed
    Then the durable event/channel identity is deduplicated

  @NJOB-07 @visual
  Scenario: Platform Operations domain remains accessible in Notification Channels
    When the user opens Channel Configuration in light and dark desktop/mobile modes
    Then Platform Operations clearly indicates Failed Jobs only
    And the existing form, focus state and event options follow Violet standards
```

Evidence: work SHA, holding SHA, UAT environment, job public ID, channel identity, terminal record timestamp, task enqueue state, Delivery Activity event key/attempts/outcome, sanitised logs, screenshots and human reviewer. **All scenarios: NOT RUN**. Reuse existing focused `tests/platform_operations/jobs/test_job_failure_notification.py`, Notification Channel contracts, Ruff, djLint and Celery queue verifier. Provider delivery requires an approved nonproduction destination. Do not claim PASS or release readiness without runtime execution.
