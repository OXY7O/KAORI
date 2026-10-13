# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Kubernetes — Tenant Management
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Pre/post provider identity and object diff, UI screenshot/trace, committed Tenant/Namespace fields and Audit correlation.
  # Isolation: Disposable Native Namespace only, read-back required and cleanup/recovery governed.
  @UAT-TEN-001 @positive @high @ui @non_ui @detailed @not_run
  Scenario: UAT-TEN-001 - Native Namespace adoption preserves provider authority
    Given approved disposable Native Namespace not owned by KAORI, baseline UID/resourceVersion, test operator with adoption permission
    And no Capsule ownership
    When capture Kubernetes Namespace UID/resourceVersion, labels/owner references and applicable quota before test
    And navigate to Tenant Discovery/Adoption and select the exact Namespace
    And review Preflight and explicitly confirm the allowed adoption
    And inspect KAORI Tenant/Namespace committed record, generation and Activity
    And read back provider Namespace by exact UID
    Then exactly one adopted generation under correct cluster/provider/tenant scope
    And committed evidence identifies the verified provider object; no duplicate governance owner
    And only explicitly admitted provider writes occur; audit/mutation provenance is truthful

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Version before/after, browser trace, response, DB diff, provider diff and Audit.
  # Isolation: Use only approved test Namespace; do not create a conflict on real operational workloads.
  @UAT-TEN-002 @negative @high @ui @non_ui @detailed @not_run
  Scenario: UAT-TEN-002 - Stale Native Namespace preflight must fail closed
    Given approved disposable Native Namespace
    And controlled test fixture may change its resourceVersion between valid Preflight and submit
    When record baseline provider UID, resourceVersion and KAORI adopted records
    And complete Discovery and Preflight through browser
    And change Namespace resourceVersion through an approved isolated fixture
    And submit the original stale form and inspect UI response, KAORI database and provider read-back
    Then no successful adoption; actionable error rather than success toast
    And no new adopted Tenant/Namespace generation and no unauthorized provider mutation
    And audit does not falsely claim successful adoption; failed attempt can be correlated

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-TEN-003 @positive @high @ui @non_ui @draft @not_run
  Scenario: UAT-TEN-003 - Create Tenant/Namespace from approved Resource Profile within budget
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities
    When create Tenant/Namespace from approved Resource Profile within budget
    Then committed pinned profile version, allocation and provider read-back match

  # Scope: Both; risk: High; expanded first-wave steps.
  # Required evidence: Form/preview screenshot, validation response, capacity source fingerprint, committed version and provider read-back.
  # Isolation: Never use a production allocation for boundary-failure testing.
  @UAT-TEN-004 @negative @high @ui @non_ui @detailed @not_run
  Scenario: UAT-TEN-004 - Capacity budget rejection prevents allocation mutation
    Given a disposable Tenant allocation/provisioning fixture with committed capacity evidence and a proposed change exceeding available governed headroom
    When open Namespace Provisioning/Allocation Change as allowed operator
    And enter an allocation exceeding the accepted cluster budget
    And inspect preview/shortfall/readiness, then attempt submit via UI or direct request
    And compare committed allocation version and provider ResourceQuota/LimitRange before and after
    Then preview shows truthful shortfall and blocks mutation
    And server independently rejects an invalid/out-of-budget submit
    And pinned allocation and provider quota/limits remain unchanged with no success audit

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-TEN-005 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-TEN-005 - Restricted or self-approving actor attempts credential/Access Grant escalation
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities
    When restricted or self-approving actor attempts credential/Access Grant escalation
    Then server denies or requires independent approval; secrets are not exposed

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-TEN-006 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-TEN-006 - Provider patch succeeds but KAORI commit/read-back fails
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities
    When provider patch succeeds but KAORI commit/read-back fails
    Then no false complete state; recovery evidence identifies possible provider residue

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-TEN-007 @positive @medium @ui @draft @not_run
  Scenario: UAT-TEN-007 - Resource Profile/Create/Allocation modal is opened and completed
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities
    When resource Profile/Create/Allocation modal is opened and completed
    Then shared modal/input/validation, labels, toast and frozen allocation version rendered correctly

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-TEN-008 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-TEN-008 - Tenant released/re-adopted identity is reused or foreign Capsule owner appears
    Given native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities
    When tenant released/re-adopted identity is reused or foreign Capsule owner appears
    Then fail closed against wrong generation/foreign owner; never silently take over

