# Harbor Webhook Reconciliation — Dev Container UAT (review only)

**Authority:** #2338 (bounded UI/evidence work), under Registry #898 and Harbor workspace #950.  
**Scope:** Integrations → Registry → Harbor → Connection Detail → Configuration → Webhook Reconciliation.  
**Target:** `kaori/review/staging-uat` after review-only integration.  
**Admission:** HOLD — no Developer Check, Full Admission, staging/main PR, deployment or release.

## Preconditions and evidence discipline

- Use a **nonproduction Harbor project/repository** and a dedicated KAORI Registry connection in the explicitly authorized Dev Container UAT environment.
- Verify Harbor deployment version, support for webhook authentication headers, CA/TLS trust, and actual Harbor → KAORI network reachability. A displayed `localhost` URL is not proof of reachable ingress from a separate host/container.
- Confirm roles for credential actions (`integrations.manage`) and maintain CSRF protection; keep rate limiting (`60 per minute`) in place.
- Generate a dedicated test webhook credential. **Never include the token in screenshots, terminal history, captured HTTP headers, logs, GitHub comments, or committed evidence.** Rotate/revoke after test.
- Record the exact **issue / work-branch SHA / aggregation SHA**, environment, Harbor identity (no secret), test resources, scenario ID, UTC timestamp, expected outcome, observed HTTP/result, committed event/JobExecution/Inventory evidence, screenshot/log reference, and human reviewer.
- Do not assume an accepted HTTP response means the worker completed; inspect event `status`, `job_execution_id`, terminal job outcome and Inventory committed snapshot before PASS.
- Where a safe dedicated test worker, test Harbor service, or controlled network fault is unavailable, mark the scenario **BLOCKED**. Do not disrupt production credentials, background workers, network, or source repositories.

## Gherkin acceptance scenarios

These scenarios are **review specifications**, not automated executable step definitions. All are **NOT RUN** at authoring time.

```gherkin
Feature: Harbor webhook admission and targeted Registry reconciliation
  In order to refresh committed Registry Inventory without treating events as truth
  As a KAORI integration operator
  I want authenticated Harbor events to trigger bounded refresh and preserve scheduled repair

  Background:
    Given an authorized nonproduction Harbor connection exists in KAORI
    And Registry scheduled reconciliation remains enabled
    And only dedicated UAT Harbor artifacts may be changed

  @WEBHOOK-01 @ui @readiness
  Scenario: Configured admission is not confused with successful delivery
    Given a webhook credential has been generated for the test connection
    And no webhook event has been received for this connection
    When I view the Harbor Configuration workspace
    Then Webhook Admission can show "Ready"
    And Last Event shows "No event received yet"
    And the UI explains that delivery and Inventory completion are not verified
    And scheduled reconciliation remains the correctness and recovery path

  @WEBHOOK-02 @connectivity @negative
  Scenario: Loopback receiver URL is not presented as a cross-host endpoint
    Given the rendered webhook receiver URL uses localhost or 127.0.0.1
    When I open Harbor Configuration
    Then a warning explains that Harbor on another host or container cannot normally reach it
    And I must verify a reachable HTTPS KAORI endpoint before delivery UAT

  @WEBHOOK-03 @positive @provider
  Scenario: Valid authenticated Harbor event is accepted and correlated with refresh evidence
    Given Harbor can reach KAORI using a trusted route
    And I configured a dedicated Harbor webhook with the test admission credential
    When Harbor sends an authorized artifact event for the UAT repository
    Then KAORI responds with HTTP 202 and accepted true
    And a committed RegistryWebhookEvent records a payload digest without raw payload
    And its status is "queued" or "deduplicated_refresh" or "refresh_failed"
    And only terminal JobExecution plus committed Inventory evidence can prove refresh success

  @WEBHOOK-04 @security @negative
  Scenario Outline: Absent or incorrect admission credential is denied
    Given the test endpoint is enabled
    When an event arrives with <credential> admission header
    Then KAORI responds with HTTP 401 and accepted false
    And no new Inventory refresh is accepted for that event
    Examples:
      | credential |
      | missing    |
      | incorrect  |

  @WEBHOOK-05 @input @negative
  Scenario: Invalid JSON is not admitted
    Given the test receiver is reachable
    When a webhook body that is not a JSON object is submitted
    Then KAORI responds with HTTP 400 and error "invalid_json"
    And no Registry refresh is queued

  @WEBHOOK-06 @dedup @positive
  Scenario: Re-delivery of identical event is idempotent
    Given an authorized test event was previously ingested
    When Harbor re-delivers an identical event body for the same Registry connection
    Then KAORI responds with HTTP 202 and duplicate true
    And the same event identity is returned
    And no second targeted refresh is created solely for that duplicate

  @WEBHOOK-07 @security @rotation
  Scenario: Rotating the admission credential revokes the prior token
    Given I have integrations.manage permission and the current UAT token
    When I rotate the credential using the CSRF-protected Harbor action
    Then the new credential is displayed only once
    And event delivery using the previous credential receives HTTP 401
    And delivery using the new credential can be accepted
    And credential values are not retained in evidence

  @WEBHOOK-08 @security @disable
  Scenario: Disabling admission blocks events while scheduled repair remains active
    Given the test receiver is enabled
    When I disable webhook admission through the authorized Harbor action
    Then subsequent event delivery receives HTTP 401
    And no webhook fast-path refresh is queued
    And scheduled Inventory reconciliation remains enabled

  @WEBHOOK-09 @reliability @controlled-fault
  Scenario: Refresh enqueue failure remains visible instead of being misreported as success
    Given the webhook receiver is authenticated
    And a controlled UAT-only enqueue failure can be induced safely
    When a new valid test event is ingested
    Then the event is committed with status "refresh_failed"
    And KAORI may still respond with HTTP 202 and accepted true
    And admission success is not reported as completed refresh
    And the failure is recoverable through the authoritative scheduled path

  @WEBHOOK-10 @recovery @provider
  Scenario: Scheduled reconciliation repairs a missed webhook
    Given a test artifact changes in Harbor while its webhook event is not delivered
    When the next allowed scheduled Inventory reconciliation completes
    Then the committed Inventory is refreshed from authoritative Harbor state
    And the missed webhook is not required as evidence of Registry truth

  @WEBHOOK-11 @resilience @provider
  Scenario: Out-of-order webhook delivery does not become provider truth
    Given test artifact changes A and B occurred in Harbor
    When the webhook for B arrives before the webhook for A
    Then committed Inventory must be reconciled against current Harbor state
    And stale event content must not overwrite current provider evidence

  @WEBHOOK-12 @visual
  Scenario Outline: Configuration guidance remains accessible across modes and viewports
    Given I am signed in with an appropriate KAORI role
    When I view Harbor Configuration in <theme> mode at <viewport>
    Then the webhook receiver and admission guidance remain readable
    And the event evidence and credential actions preserve keyboard/focus access
    And the layout has no unintended horizontal overflow
    Examples:
      | theme | viewport |
      | light | desktop  |
      | dark  | desktop  |
      | light | mobile   |
      | dark  | mobile   |
```

## Execution matrix

| Scenario | Primary evidence | Initial status |
|---|---|---|
| WEBHOOK-01 | UI + persisted endpoint state | NOT RUN |
| WEBHOOK-02 | Loopback screenshot + Harbor-side reachability test | NOT RUN |
| WEBHOOK-03 | Sanitized Harbor delivery + event, job and Inventory evidence | NOT RUN |
| WEBHOOK-04 | 401 response + absence of new event/job | NOT RUN |
| WEBHOOK-05 | 400 response + no new refresh | NOT RUN |
| WEBHOOK-06 | Two 202 responses + stable event ID / job count | NOT RUN |
| WEBHOOK-07 | Authorized UI rotation + old-token 401 / new-token admission | NOT RUN |
| WEBHOOK-08 | Authorized disable + 401 + scheduled job remains eligible | NOT RUN |
| WEBHOOK-09 | Controlled enqueue failure + committed refresh_failed | NOT RUN |
| WEBHOOK-10 | Scheduled JobExecution + authoritative committed Inventory diff | NOT RUN |
| WEBHOOK-11 | Sanitized out-of-order deliveries + final Harbor/Inventory correlation | NOT RUN |
| WEBHOOK-12 | Light/dark desktop/mobile screenshots, keyboard testing | NOT RUN |

## Local validation (when Dev Container is available)

Use the canonical local change-impact planner for exact-head focused test selection, followed by the existing relevant gates. Focused examples:

```bash
python -m pytest -q tests/contracts/artifact_registry/test_registry_webhook_contract.py
python -m pytest -q tests/contracts/integrations/test_harbor_provider_workspace_contract.py
python -m ruff check tests/contracts/artifact_registry/test_registry_webhook_contract.py
python -m djlint app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html --check
```

Keep the existing Repository/Dev Container prerequisites and configured commands authoritative if tool invocation differs. Include source-contract result, local server+worker logs, human Visual QA evidence, and any resulting defect issue. No scenario is PASS unless actually executed and evidenced.

## Evidence record template

- Issue: #2338
- Work branch + SHA: **PENDING exact tested commit**
- Holding branch + SHA: **PENDING integration**
- Dev Container image/environment identity: **PENDING**
- Harbor instance, host reachability, TLS/header support (no secret): **PENDING**
- Scenario ID + execution timestamp: **PENDING**
- Expected / actual response and committed JobExecution / Inventory evidence: **PENDING**
- Outcome (PASS / FAIL / BLOCKED / NOT RUN): **NOT RUN**
- Screenshot/log/evidence URI (redacted): **PENDING**
- Human reviewer / acceptance: **PENDING**

**Decision boundary:** this document authorizes no production mutation and no official admission. Local UAT PASS never replaces Developer Check, Full Admission, required staging UAT or human acceptance.
