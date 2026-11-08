# Kubernetes Operations — ConfigMap CRUD DevContainer UAT

**Authority:** #1018 (Kubernetes Operations overview and destructive confirmation), #2360 (compact safety copy); governed Gherkin specification #1738 (`UAT-KOP-001`, `UAT-KOP-002`).  
**Human decision:** **ConfigMap Create → Update → Delete functional UAT ACCEPTED** (operator request to close on **2026-10-25, Asia/Jakarta**).  
**Environment:** DevContainer KAORI temporary UAT branch `kaori/review/staging-uat`, registered UI cluster **Kubernetes X300**. Operator shell reports kubecontext `docker-desktop`; label equivalence was not independently established by cluster identity comparison.  
**Real test object:** `default/application-config`, key `DB_NAME`; data values deliberately omitted from this evidence record. This resource was created during the UAT, subsequently updated, then deleted. **The test was executed in namespace `default`, NOT in an isolated disposable namespace**; do not generalize the record as successful sandbox isolation.  
**Source of evidence:** Operator-provided Firefox screenshots and `kubectl` CLI outputs from 2026-10-25 UAT conversation. Exact browser/source candidate SHA was not recorded at every interaction; these screenshots are **manual evidence**, not machine test execution or official admission evidence.

## Human UAT outcomes

| Activity | Observed evidence | Outcome |
| --- | --- | --- |
| Create form | Live target selected; key entry; change resets validated state to Pending and disables Create | PASS (visible UI) |
| Create validation | Kubernetes server-side dry-run says ConfigMap Validation Passed; 1 key, 12 B, Mutable; Create enabled | PASS (visible UI) |
| Create mutation | `ConfigMap Created · Success`, form cleared, Activity Register event `kubernetes_configmap_created` | PASS |
| Create readback | `default/application-config` exists, UID `a617370d-0fd0-4904-8d35-32336240ccba`, creation `2026-10-25T00:47:52Z`, resourceVersion `3353607`, `dataKeys=[DB_NAME]`, no binary keys | PASS |
| Update preview | Merge Selected Keys, effective diff 0 added / 1 changed (`DB_NAME`) / 0 removed; Update validated and enabled | PASS (visible UI) |
| Update mutation | `ConfigMap Updated · Success`, clean target form; Activity Register `kubernetes_configmap_updated` | PASS |
| Update readback | Same UID, resourceVersion advanced to `3355995`, key list remains `[DB_NAME]` | PASS for identity/version/key; changed **value not independently read back** |
| Delete preflight | Exact-name confirmation, 1 live key, best-effort Inventory count 0, signed 10-minute receipt; validation-success UI | PASS for displayed preflight; no network trace proving no DELETE issued during validation |
| Final Delete | Explicit destructive confirmation modal, user submitted Delete; Activity Register `kubernetes_configmap_deleted`, `ConfigMap Deleted · Success` | PASS |
| Deleted readback | `kubectl -n default get configmap application-config` → `Error from server (NotFound)` | PASS |

**Cross-domain evidence:** Create audit recorded **25 Oct 2026 07:47 WIB**; Kubernetes creation time **00:47:52 UTC** (07:47:52 WIB). Update audit recorded **08:03 WIB**. Delete audit recorded **08:50 WIB**. Audit detail panels identify actor **Super Administrator / Local Database Super Admin**, target ConfigMap, module ConfigMap Management, source Administrative action and the three event keys above. User-visible audit record does not expose ConfigMap field values. The retained audit metadata aligns with the observed provider resource identity and lifecycle.

**Important interpretation:** `0 Workload References` came from a **committed Pod snapshot**, not a live dependency enumeration. It does not rule out external consumers. Successful deletion and `NotFound` prove the action completed, not that workloads were unaffected. The real-world action already occurred; this document does not authorize further mutation. The audit UI showed metadata only, but complete historical DB/log/export absence of values still needs separate security assertions.

## Gherkin — human-executed positive CRUD flows

These manually observed scenarios refine the **existing** `UAT-KOP-001` positive capability specification; they are not a second executable BDD runner. Exact-ID JUnit/Playwright attribution is **NOT RUN**. `UAT-KOP-002` remains the unexecuted negative/concurrency contract.

```gherkin
Feature: Kubernetes Operations — controlled ConfigMap CRUD and evidence
  KAORI validates exact live targets while Kubernetes owns mutations,
  Inventory supplies best-effort impact, and Activity Audit records outcomes.

  Background:
    Given a permitted Super Administrator uses Kubernetes Operations
    And the registered cluster is Kubernetes X300
    And the selected live namespace is default
    And the UAT ConfigMap target is application-config
    And no ConfigMap value will be copied into the audit artifact

  Scenario: Create only after a successful server-side dry-run
    Given the Create ConfigMap form has not yet been validated
    When the operator enters the DB_NAME text key
    Then Create ConfigMap remains disabled until validation passes
    When the operator validates the latest form state
    Then the dry-run shows 1 key and Mutable, and enables Create
    When the operator submits Create ConfigMap
    Then the UI reports ConfigMap Created with Success
    And the form returns to a clean new-create state
    And Activity Audit records kubernetes_configmap_created with actor and target
    And provider readback finds default/application-config and key name DB_NAME

  Scenario: Merge validates the effective change before updating
    Given default/application-config is readable from the live Kubernetes API
    And its object identity and resourceVersion are bound to the update form
    When the operator selects Merge Selected Keys and changes DB_NAME
    And the operator runs Preview and Validate
    Then the diff shows 0 added, 1 changed, and 0 removed keys
    And Apply Update is enabled for the last validated form state
    When the operator applies the validated update
    Then the UI reports ConfigMap Updated with Success and resets the form
    And Activity Audit records kubernetes_configmap_updated
    And provider readback preserves UID and advances resourceVersion
    And key-name metadata still contains DB_NAME

  Scenario: Delete requires exact-name validation and final confirmation
    Given default/application-config exists in the live cluster
    And the displayed zero workload references are labeled inventory-backed
    When the operator types application-config as exact-name confirmation
    And the operator validates deletion
    Then the UI reports ConfigMap Deletion Validated
    And the receipt reports a 10-minute validity bound to the target and version
    And the final destructive action becomes available
    When the operator opens the Delete ConfigMap confirmation
    Then the modal identifies the exact resource and namespace
    And it warns that deletion is permanent
    When the operator confirms deletion
    Then the UI reports ConfigMap Deleted with Success
    And Activity Audit records kubernetes_configmap_deleted with actor and target
    And Kubernetes returns NotFound for default/application-config

  Scenario: Cross-domain mutation audit retains metadata without values
    Given a ConfigMap Create, Update, and Delete have been completed
    When the operator opens their Activity Register details
    Then the actor, action, target and event key are attributable to each outcome
    And the Create, Update and Delete records are associated with Kubernetes X300
    And the displayed activity details do not disclose ConfigMap values
    And the activity history remains after the live object is deleted
```

## Acceptance boundary / admission backlog

**Human UAT decision: ACCEPTED for the positive ConfigMap CRUD session described above.** No further manual confirmation is required to accept those already observed positive steps. The following are **not** covered by this sign-off:

- `UAT-KOP-002` negative tests: denied actor, stale resourceVersion/UID, conflicting edit, wrong target, forged or expired receipt, duplicate-create protection, immutability refusal, CSRF violation.
- No independent request/network trace confirming **no DELETE** was sent during preflight; the implementation contract requires this and must be covered by existing pytest/security gates.
- Full API readback of the changed `DB_NAME` **value**; intentionally not captured in screenshots or audit.
- Full authorization matrix, light/dark/responsive and modal keyboard/focus matrix.
- Proof `docker-desktop` kubecontext is exactly the KAORI registered Kubernetes X300 cluster via verified API server/UID (not inferred from a label).
- One-line Delete copy requested at UAT end is implemented as a separate issue-backed UI follow-up under #2360 and needs a fresh DevContainer visual and formatter/contract check. Its human visual acceptance is separate from already accepted CRUD functionality.
- Official CI/CD Developer Check, Full Admission, Staging promotion, release/tag and GitHub Project custom-field synchronization remain on HOLD until explicit authorization.

**Documentation and traceability:** Canonical Gherkin authority remains `docs/engineering/uat/features/kop-kubernetes-operations.feature` under #1738; use that for risk-based executable acceptance specification. This session log records observed Gherkin behavior and evidence, not a parallel test taxonomy.

**Next UAT domain:** Kubernetes Operations → Secret Management (Create / Replace / Delete / Protected Reveal / TLS), under existing approved permission and protected-value boundaries.
