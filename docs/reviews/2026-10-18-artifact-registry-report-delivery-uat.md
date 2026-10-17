# Notification Channels — Artifact Registry Report Delivery UAT

**Issue authority:** #2342, derived from cross-domain producer audit #2331. Existing schedule-domain fix #1649 / merged PR #1655 is reused, not replaced.  
**Scope:** `Integrations → Delivery → Notification Channels` and existing `Reports → Schedules`.  
**Holding target:** `kaori/review/staging-uat` (review-only, no official admission).  
**Current results:** **NOT RUN**. This is an executable acceptance specification, not claimed runtime evidence.

## Source and routing boundaries

- Published Artifact Registry reports use **`artifact_registry`** (`app/definitions/catalogs/reports/catalog.yaml`); `app/reports/notifications.py` emits `report.generated` with `domain=report.report_domain`. That is the first qualified new routing domain.
- Recommendation-origin Alert Intelligence cases use **`registry`**, a deliberately different domain. Registry alert routing, including default fallback, stays **denied** in `app/intelligence/alert_intelligence/routing.py` pending #1186/#1512 and scoped governance.
- The shared outbound catalog qualifies Artifact Registry for **`report.generated` only**. Other eleven-catalog event families are not automatically valid for the new domain.
- Existing Kubernetes and Object Storage channel selections, event matching, severity, encryption and provider transports must not change.
- `NotificationDelivery` records are external delivery evidence. Activity Audit remains separately authoritative; provider acknowledgment is not proof that a human read the message.

## Gherkin scenarios

```gherkin
Feature: Source-qualified Artifact Registry Report Ready delivery

  Background:
    Given an authorized Dev Container contains a nonproduction Artifact Registry report source
    And a nonproduction Notification Channel provider destination is configured and validated
    And official admission and deployments remain on HOLD

  @NDD-01 @positive @configuration
  Scenario: Artifact Registry appears with truthful allowed use
    When an authorized operator opens Add Notification Channel
    Then Artifact Registry appears under Delivery Domains with "Report Ready only"
    And the channel's allowed uses include "Scheduled Reports · Report Ready"
    And Registry AlertCase routing is not advertised as enabled

  @NDD-02 @negative @policy
  Scenario: Artifact Registry cannot be configured for alerts alone
    Given the channel chooses Artifact Registry as its only Delivery Domain
    When the operator chooses "Alert Operations · Firing" without Report Ready
    Then configuration validation rejects the unsupported domain/event combination
    And no channel delivery policy change is persisted

  @NDD-03 @positive @report
  Scenario: Scheduled Artifact Registry report reaches the selected matching destination
    Given the channel permits Artifact Registry and Scheduled Reports · Report Ready
    And a scheduled Artifact Registry report is generated to a committed ready artifact
    When the authorized Reports worker delivers the report-generated event
    Then only enabled configured validated matching destinations are eligible
    And the source domain is "artifact_registry" with event "report.generated"
    And a committed NotificationDelivery records channel and report identity
    And a user with reports.view can follow a matching permissioned Open Report link

  @NDD-04 @negative @security
  Scenario: Registry recommendation AlertCase cannot deliver via a report-only channel
    Given a channel supports "artifact_registry" and "report.generated"
    When an AlertCase emits domain "registry" and event "alert_ops.firing"
    Then the Registry routing policy denies the event
    And no NotificationDelivery is sent for that denied event

  @NDD-05 @negative @cross-domain
  Scenario: A mixed channel filters unsupported pairs without broad fallback
    Given a channel selects Kubernetes and Artifact Registry
    And its selected events include Firing and Report Ready
    When an Artifact Registry Firing event is offered to the dispatcher
    Then the event is refused even though Kubernetes supports Firing
    And a valid Artifact Registry Report Ready event remains eligible
    And a valid Kubernetes Firing event retains existing behavior

  @NDD-06 @negative @lifecycle
  Scenario: Disabled or unvalidated channels are never silently delivered
    Given an Artifact Registry report channel is disabled or not validated
    When a qualified Report Ready event is emitted
    Then the channel is not selected for delivery
    And no provider delivery success is asserted

  @NDD-07 @regression @visual
  Scenario Outline: Channel configuration preserves the Violet design system
    When the Add/Edit Channel dialog renders in <theme> at <viewport>
    Then all allowed Delivery Domains and Allowed Uses remain readable
    And their labels, focus states and error messages are accessible
    And no unauthorized domain option or unexpected overflow appears

    Examples:
      | theme | viewport |
      | light | desktop  |
      | dark  | desktop  |
      | light | mobile   |
      | dark  | mobile   |
```

## Local execution and evidence matrix

| Scenario | Evidence to collect | Initial result |
| --- | --- | --- |
| NDD-01 | Screenshot of catalog-backed form + selected policy | NOT RUN |
| NDD-02 | Invalid POST result, validation message, unchanged saved channel | NOT RUN |
| NDD-03 | ReportScheduleRun + Report + NotificationDelivery + provider ACK (redacted) | NOT RUN |
| NDD-04 | Registry AlertCase routing block + zero unauthorized deliveries | NOT RUN |
| NDD-05 | Domain/event matcher results and mixed-channel per-event delivery count | NOT RUN |
| NDD-06 | Disabled/unvalidated channel result and journal verification | NOT RUN |
| NDD-07 | Desktop/mobile light/dark, accessibility and keyboard screenshots | NOT RUN |

Record issue #2342, tested work branch and exact SHA, aggregation SHA, Dev Container image/environment, provider/source readiness, expected and actual, PASS/FAIL/BLOCKED/NOT RUN, sanitized logs/screenshots, defect links and human acceptance. Do not include email passwords, webhook URLs with tokens, credentials, privileged error bodies or customer report contents.

### Existing focused validation, when Dev Container is available

```bash
python -m pytest -q tests/integrations/notification_channels/test_artifact_registry_notification_domain.py
python -m pytest -q tests/integrations/notification_channels/test_notification_channel_functional_characterization.py
python -m pytest -q tests/contracts/reports/test_report_schedule_strict_post_domains_contract.py
python -m pytest -q tests/contracts/integrations/test_notification_channels_audit_20260817_contract.py
python -m ruff check app/integrations/delivery/notification_channels tests/integrations/notification_channels/test_artifact_registry_notification_domain.py
python -m djlint app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html --check
```

The canonical change-impact planner, pytest, Ruff, djLint, Pyright, browser Visual QA, developer checks and Full Admission remain the existing standard; this matrix does not replace them. Never mark **PASS** without actual execution/evidence. Dev Container local UAT does **not** authorize staging/full admission, deployment, main promotion or release.
