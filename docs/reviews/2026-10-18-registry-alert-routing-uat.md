# Registry AlertCase → Notification Channels — Dev Container UAT

**Authority:** #2344 under #2331, #1186, #1512. **Delivery:** review-only `kaori/review/staging-uat`. **Official admission:** HOLD.

Canonical routing domain **`registry`** is different from Reports `artifact_registry`. Registry alert producer is the committed **recommendation-origin** `AlertCase`, not provider-native Alertmanager/Harbor, and not a Report Ready event. The current integration identity is an enabled/active/nonblocked `IntegrationInstance` of type registry. This policy is opt-in; **no default broadcast**.

## Preconditions
Dedicated UAT Registry/Harbor identity with known committed recommendations and AlertCases, approved provider destination with successful Test Delivery and no production credentials, isolated explicit routing policy for `registry`, permissioned management account, and existing Alert Intelligence worker. Record exact tested work SHA and holding aggregation SHA; never record provider tokens, raw assets, or sensitive alert payload.

```gherkin
Feature: Governed Registry AlertCase delivery

  Background:
    Given a nonproduction active Registry IntegrationInstance has a committed recommendation-origin AlertCase
    And a Registry-scoped Notification Channel has been configured and validated
    And the routing policy can be managed only by authorized operators

  @NREG-01 @positive
  Scenario: Explicit matching policy delivers Registry firing
    Given the operator created a dedicated enabled policy for "registry" and a validated Registry channel
    And the policy matches the committed AlertCase severity and labels
    When the AlertCase is firing and not suppressed or silenced
    Then the governed dispatcher may deliver "alert_ops.firing" with domain "registry"
    And one channel-owned NotificationDelivery record correlates to the durable case

  @NREG-02 @negative
  Scenario: No explicit Registry policy means no default broadcast
    Given no enabled matching Registry routing policy exists
    When a Registry AlertCase becomes firing
    Then no default channel receives Registry alert delivery

  @NREG-03 @negative
  Scenario Outline: Ineligible Registry provider cannot route
    Given the Registry IntegrationInstance is <state>
    When its case is evaluated for routing
    Then Registry alert delivery is denied
    Examples:
      | state      |
      | disabled   |
      | retired    |
      | blocked    |
      | unknown ID |

  @NREG-04 @negative
  Scenario: Registry policy cannot mix other domain scope
    When an operator submits a routing policy with Registry and Kubernetes simultaneously
    Then policy validation rejects the cross-domain configuration

  @NREG-05 @negative
  Scenario: Wrong event or channel domain cannot qualify
    Given a channel is configured for "artifact_registry" Report Ready only
    When a Registry firing AlertCase is evaluated
    Then the report channel is ineligible even if the destination is otherwise reachable

  @NREG-06 @negative
  Scenario: Source Unknown or operator suppression cannot fire
    Given the case is Source Unknown or routing is suppressed
    When the dispatcher checks Registry routes
    Then no firing delivery occurs

  @NREG-07 @positive
  Scenario: Resolved route preserves prior successful firing and current policy
    Given a Registry firing AlertCase was delivered successfully on its authorized channel
    And the policy permits resolved delivery and still matches
    When source-state resolves and closure evidence is committed
    Then at most one resolved event is sent to the qualifying channel
    And failed channel attempts remain independently retryable
    And no new resolved recipients are fabricated from policy changes

  @NREG-08 @security
  Scenario: Disabled or mismatched policy cannot fallback broadly
    Given an explicit Registry policy exists but is disabled or does not match the case
    When the dispatcher evaluates the case
    Then no channel-wide fallback occurs

  @NREG-09 @visual
  Scenario Outline: Registry routing UI is usable across modes
    When the Routing & Channels workspace is shown in <theme> at <viewport>
    Then Registry is available as a governed domain in the policy editor and filter
    And tab actions, dialogs, error states and keyboard focus follow Violet standards
    Examples:
      | theme | viewport |
      | light | desktop  |
      | dark  | desktop  |
      | light | mobile   |
      | dark  | mobile   |
```

## Evidence

| Scenario | Expected evidence | Initial |
| --- | --- | --- |
| NREG-01 | Committed AlertCase, policy, Test Delivery, NotificationDelivery | NOT RUN |
| NREG-02 | No matching policy/no unexpected journal | NOT RUN |
| NREG-03 | Inactive/unknown instance and zero send | NOT RUN |
| NREG-04 | Rejected POST, unchanged stored policy | NOT RUN |
| NREG-05 | Wrong-domain channel filtering | NOT RUN |
| NREG-06 | Case source/routing state, absence of delivery | NOT RUN |
| NREG-07 | Firing→resolved exact case/channel journal, duplicate/retry protection | NOT RUN |
| NREG-08 | Disabled/mismatched policy, no fallback | NOT RUN |
| NREG-09 | Light/dark mobile/desktop Visual QA and keyboard screenshots | NOT RUN |

Run existing focused Intelligence and Notification Channels pytest, Ruff, djLint, Pyright and source verification in Dev Container. Manual provider exercise and human review required for security-sensitive routing. **NOT RUN does not mean PASS.** No official Developer Check, Full Admission, staging/main/release/deployment.
