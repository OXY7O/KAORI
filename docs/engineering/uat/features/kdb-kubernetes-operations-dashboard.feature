# KAORI UAT — Kubernetes Operations Dashboard
# Scenario authority #1738, dashboard acceptance #937/#753, evidence contract #1725.
# The operator Human Accepted the Dashboard on 2026-10-24.
# This reusable specification does NOT retroactively certify unrun Scenario IDs.
# Tests execute in existing pytest/Playwright suites, not a new Gherkin runner.

Feature: Kubernetes Operations Dashboard
  The Overview is a read-only, permission-scoped projection over committed
  Kubernetes inventory, metrics, AlertCases, recommendations and report evidence.

  Background:
    Given a KAORI Dev Container candidate with its exact source SHA and actor recorded
    And an authorized cluster catalog and committed dashboard evidence fixture exist
    And external Kubernetes, Metrics and alert providers remain authoritative

  # Layer: UI; risk: High; the signed-in shell has four bounded dashboard tabs.
  # Evidence: shell, KPI and scoped source screenshots plus request/section trace.
  @UAT-KDB-001 @positive @high @ui @specified @owner_review
  Scenario: UAT-KDB-001 - Dashboard shell and eight signals reflect active committed scope
    Given an operator with Kubernetes Dashboard view permission selects a known cluster
    When the operator opens "/dashboards/kubernetes/" and waits for KPI evidence
    Then the Violet Dashboard Hero and source-qualified cluster scope are visible
    And the eight KPI cards show inventory, worker metrics and alert source labels
    And the initial shell does not rely on an unconditional live provider query
    And selected scope and freshness labels are consistent across sections

  # Layer: Both; risk: High; connection posture differs from composite incident severity.
  # Evidence: committed cluster readiness, AlertCase severity and dashboard table/HTML.
  @UAT-KDB-002 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KDB-002 - Cluster connectivity remains distinct from operational alert severity
    Given a connected cluster with ready nodes and a committed Critical AlertCase
    When the operator opens Operations Overview and Cluster Health Summary
    Then the cluster connection and node-readiness counts reflect their own sources
    And Overall cluster health identifies Critical with the incident reason
    And no green connection status suppresses a real Critical operational signal
    And the health table remains cluster-scoped with default five rows

  # Layer: Both; risk: Medium; worker-only analytics are evidence-based, not fabricated.
  # Evidence: capacity/forecast committed source, responsive cards, chart and narrative.
  @UAT-KDB-003 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-KDB-003 - Capacity and forecast present worker-only committed projections
    Given selected-cluster worker metrics and forecast evidence with a known horizon
    When the operator selects Capacity & Demand
    Then CPU memory and pod capacity reflect worker nodes excluding control-plane roles
    And the forecast chart separates historical samples and forward projections
    And the conclusion uses the real highest projected resource, percentage and horizon
    And cards and capacity action flow preserve the canonical compact layout

  # Layer: UI; risk: High; AlertCase and shared governed response evidence.
  # Evidence: severity totals, bounded recent rows, six-step guidance and source callout.
  @UAT-KDB-004 @positive @high @ui @specified @owner_review
  Scenario: UAT-KDB-004 - Alert totals and controlled response retain source and severity
    Given selected-cluster committed AlertCases with known severity and lifecycle state
    When the operator opens Signals & Actions
    Then totals are grouped correctly as Critical Warning and Info
    And recent open case preview contains no more than five entries
    And the six governed steps are Validate Triage Investigate Respond Verify Record
    And critical incident triage does not falsely imply healthy provider alerts

  # Layer: UI; risk: Medium; shared recommendation renderer owns Intelligence handoff.
  # Evidence: five-card screenshot, full title hover, actual link destination and scope.
  @UAT-KDB-005 @positive @medium @ui @specified @owner_review
  Scenario: UAT-KDB-005 - Recommendation previews stay compact with full Intelligence details
    Given selected-scope central Intelligence recommendation findings
    When the operator views the Recommended Actions cards
    Then no more than five prioritized recommendation cards are shown
    And each title and description preview occupies at most two lines
    And original full recommendation text remains available without source truncation
    And priority category source footer and canonical Intelligence detail link remain

  # Layer: Both; risk: High; a Ready record is not universal proof of available storage.
  # Evidence: selected reporting scope, Report row/status, actual download result.
  @UAT-KDB-006 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KDB-006 - Kubernetes report activity leads to a downloadable Ready artifact
    Given a cluster-scoped Kubernetes report record in Ready status with stored artifact
    When the operator opens Reporting and then Open Reports Workspace
    And downloads the selected Ready report artifact using an authorized identity
    Then report activity is limited to the Kubernetes domain and selected cluster
    And recent activity shows no more than four reports in stable newest-first order
    And the selected report download succeeds for that artifact
    And source availability, lifecycle status and storage accessibility stay distinct

  # Layer: UI; risk: Medium; existing shared tab/visual baseline and browser semantics.
  # Evidence: screenshots/trace in six canonical viewports, both themes and URL state.
  @UAT-KDB-007 @positive @medium @ui @specified @owner_review
  Scenario: UAT-KDB-007 - Four workspace tabs preserve navigation and responsive themes
    Given a signed-in Dashboard with approved Violet light and dark themes
    When the operator switches among the four tabs across canonical viewports
    Then one active tab is visually distinguished and the matching panel is shown
    And the URL, Back, Forward and refresh recover the selected workspace
    And titles, tables, forecast, actions and scroll regions do not horizontally clip
    And visual-baseline changes require explicit review instead of silent regeneration

  # Layer: Both; risk: High; lack of committed evidence is not zero or green.
  # Evidence: missing/stale fixture read-back, empty panel, readiness and request trace.
  @UAT-KDB-008 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KDB-008 - Missing or stale evidence cannot fabricate healthy metrics
    Given the chosen cluster lacks current metrics forecast or alert-source evidence
    When an authorized operator requests the dependent Dashboard sections
    Then the affected section renders an honest unavailable or partial evidence state
    And absent evidence is not converted to zero utilization or Normal health
    And unrelated committed inventory remains available without provider mutation
    And no source-unavailable state is mistaken for an empty successful result

  # Layer: Both; risk: High; selection is an authorization and correlation boundary.
  # Evidence: selected-cluster and all-cluster queries, committed row scope and traces.
  @UAT-KDB-009 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KDB-009 - Invalid or switched cluster scope cannot leak foreign evidence
    Given committed inventory reports alerts and capacity data for distinct clusters
    When the operator changes Selected Cluster and then tests All Clusters scope
    And submits a stale unknown or unauthorized cluster identifier
    Then sections display only the identity and evidence allowed by the current scope
    And detailed Capacity and Signals require a valid selected cluster
    And All Clusters reporting aggregates only Kubernetes-domain records
    And no unknown cluster silently falls back to unrelated private evidence

  # Layer: Both; risk: High; permission rejection precedes heavy evidence reads.
  # Evidence: HTTP 403/redirect, denied page, no provider/DB side effect and trace.
  @UAT-KDB-010 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KDB-010 - Restricted actors cannot bypass Dashboard access or start mutations
    Given a restricted principal without Kubernetes Dashboard view permission
    When the principal requests the Dashboard shell and lazy section URLs directly
    Then server-side authorization denies the protected dashboard data
    And permission checks precede heavy section builders and provider reads
    And no hidden tab or direct URL creates a job or mutates Kubernetes state
