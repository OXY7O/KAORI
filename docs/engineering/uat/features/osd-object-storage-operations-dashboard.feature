# Object Storage Operations Dashboard reusable Gherkin
# Authority #3168 / #1738; family #753 / #923; NOT machine UAT PASS.
# Desktop visual review accepted four tabs, other negative and delivery paths NOT RUN.

Feature: Object Storage Operations Dashboard
  Read-only committed inventory analytics forecast and Alert Intelligence projections.

  Background:
    Given a recorded exact source SHA actor and selected Object Storage identity
    And sanitized committed evidence and isolated negative fixtures
    And external providers remain authoritative with no unapproved writes

  # UI risk High; screenshots source and JUnit required for actual execution.
  @UAT-OSD-001 @positive @high @ui @specified @owner_review
  Scenario: UAT-OSD-001 - Dashboard shell and four KPIs use committed scope
    Given registered MinIO X300 with committed inventory analytics and AlertCases
    When an authorized operator opens /dashboards/object-storage/
    Then the Violet Hero displays selected scope and Committed Snapshots authority
    And four KPIs expose buckets usage utilization and KAORI AlertCases
    And evidence age and source labels are visible without an unconditional live provider query

  # Both risk High; screenshots source and JUnit required for actual execution.
  @UAT-OSD-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OSD-002 - Stale analytics does not conceal warning posture
    Given connected Object Storage with committed inventory and stale analytics
    When the operator opens Operations Overview
    Then the health table displays Warning for stale analytics
    And freshness remains distinct for Inventory Analytics Forecast and Alert Evidence
    And usable fleet analytics is not misrepresented as fresh

  # Both risk Medium; screenshots source and JUnit required for actual execution.
  @UAT-OSD-003 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-OSD-003 - All Systems and selected-scope switching stays correlated
    Given two committed Object Storage systems with distinct buckets and AlertCases
    When the operator switches All Systems and back to MinIO X300
    Then All Systems shows Systems Buckets Inventory Usage and Analytics Ready
    And selected system returns Buckets Used Capacity Utilization and Active Alerts
    And system health table uses five-row pagination and no foreign data

  # Both risk Medium; screenshots source and JUnit required for actual execution.
  @UAT-OSD-004 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-OSD-004 - Capacity forecast and Top Consumers use committed measurements
    Given scoped used free usable capacity and 30-day forecast snapshots
    When the operator selects Capacity & Demand
    Then capacity balance and projections use committed source measurements
    And the graph differentiates historical and forward forecast
    And 90-day forecast conclusion and dynamic bucket share preserve uncertainty

  # UI risk High; screenshots source and JUnit required for actual execution.
  @UAT-OSD-005 @positive @high @ui @specified @owner_review
  Scenario: UAT-OSD-005 - Signals retain AlertCase severity and governed response
    Given selected-system active warning AlertCase and central recommendation findings
    When the operator opens Signals & Actions
    Then severity and up to five previews derive from KAORI AlertCase records
    And Validate Triage Investigate Respond Verify Record steps remain ordered
    And response guidance never initiates a provider mutation

  # UI risk Medium; screenshots source and JUnit required for actual execution.
  @UAT-OSD-006 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OSD-006 - Recommendations use shared bounded previews and Intelligence detail
    Given Object Storage Intelligence findings with long descriptions and full rule detail
    When the operator inspects Recommended Actions and opens Intelligence detail
    Then title and description previews use two-line clamp like Kubernetes
    And source uses presentational truncation and full title is accessible
    And original action text priority category and detail handoff remain intact

  # Both risk High; screenshots source and JUnit required for actual execution.
  @UAT-OSD-007 @positive @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OSD-007 - Reporting empty state is distinct from a Ready report download
    Given a clean empty Object Storage report scope and isolated Ready artifact fixture
    When the operator opens Reporting then retrieves the Ready report
    Then zero report counts show actionable no-report empty state
    And governed Validate Select Create Generate Schedule Retain steps remain
    And only actual authorized artifact download can establish Ready retrieval

  # UI risk Medium; screenshots source and JUnit required for actual execution.
  @UAT-OSD-008 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OSD-008 - Four tabs retain URL theme and responsive behavior
    Given permitted actor with supported light dark and narrow viewport fixtures
    When the operator navigates all four tabs including Back Forward and refresh
    Then only one active tab and matching lazy section is visible
    And valid selected scope survives navigation history and refresh
    And cards guidance charts and table text remain accessible without clipping

  # Both risk High; screenshots source and JUnit required for actual execution.
  @UAT-OSD-009 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OSD-009 - Missing or invalid Object Storage scope cannot fake metrics
    Given missing analytics evidence with a separate invalid or foreign system ID
    When the operator requests a scoped section with missing data or invalid identity
    Then missing measurements show unavailable rather than zero or Healthy
    And detailed sections require a valid selected system
    And All Systems does not expose unauthorized or unrelated committed records

  # Both risk High; screenshots source and JUnit required for actual execution.
  @UAT-OSD-010 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OSD-010 - Restricted direct Dashboard and section requests are denied
    Given a restricted principal without dashboard.view permission
    When the actor directly requests Dashboard and lazy-section URLs
    Then authorization denies protected content before expensive reads
    And bucket AlertCase recommendation and report identities do not leak
    And read-only requests create no job provider mutation or generated report
