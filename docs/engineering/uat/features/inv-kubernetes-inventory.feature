# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Kubernetes — Dashboard, Inventory & Topology
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-INV-001 @positive @medium @ui @specified @owner_review
  Scenario: UAT-INV-001 - Operator opens Cluster/Dashboard then Inventory lists and details
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; committed objects with distinct UIDs on two clusters
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator opens Cluster/Dashboard then Inventory lists and details
    And perform the scenario action using an approved browser or domain test client: Operator opens Cluster/Dashboard then Inventory lists and details
    And open object detail on cluster A then repeat on cluster B
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-001
    Then correct selected-cluster scope, navigation, row/detail identity and shared table UI
    And object, row, breadcrumb and source IDs never cross clusters
    And the shared Inventory workspace covers Overview, Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage and Configuration
    And every resource modal exposes identity, current-generation snapshot context, relationships and a safe operational boundary
    And Close and Escape dismiss an opened and reopened detail without losing scope
    And ConfigMap and Secret Inventory reveal key names and safe metadata, never their protected values
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INV-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-INV-002 - Inventory evidence is stale, missing or partially collected
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; stale, partially collected and absent inventory snapshots
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Inventory evidence is stale, missing or partially collected
    And perform the scenario action using an approved browser or domain test client: Inventory evidence is stale, missing or partially collected
    And open each state and inspect freshness and missing-object displays
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-002
    Then uI explicitly displays stale/partial/unknown, not fabricated Healthy/zero
    And unknown is not fabricated zero/healthy and partial evidence is labeled
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INV-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-INV-003 - Same-name object is recreated with a different provider UID
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; same object name recreated with a new Kubernetes UID
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Same-name object is recreated with a different provider UID
    And perform the scenario action using an approved domain/service test client: Same-name object is recreated with a different provider UID
    And compare previous and new generation in detail/correlation
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-003
    Then old/new identities are not conflated; lineage and correlation remain correct
    And lineage differentiates both UIDs without reusing old identity
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-INV-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-INV-004 - Filter/sort/page Inventory records including zero-result state
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; at least 11 inventory rows plus unmatched search
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Filter/sort/page Inventory records including zero-result state
    And perform the scenario action using an approved browser or domain test client: Filter/sort/page Inventory records including zero-result state
    And sort/filter, change page and Rows then clear filters
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-004
    Then filters persist across HTMX navigation; pagination and No Results follow shared standard
    And hTMX preserves selection and no-result/page-reset semantics
    And Resource Type, lifecycle, class, Namespace and search filters preserve correct resource identities
    And clear filters resets the resource-specific defaults and returns to the first page
    And the standard table defaults to five rows while configured Rows options remain available
    And Topology Resource List and Details/Relationships Inspector remain usable for dense graphs
    And dense Full Relationships Hierarchy and Dependency layouts offer readable focal exploration
    And explicit Fit distinguishes a complete graph overview from readable focus without omitting committed resources
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-INV-005 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-INV-005 - Topology relationship source is absent or inconsistent
    Given selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects; topology missing one relationship and similarly named foreign-cluster node
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Topology relationship source is absent or inconsistent
    And perform the scenario action using an approved browser or domain test client: Topology relationship source is absent or inconsistent
    And remove relationship source then inspect graph and detail
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-INV-005
    Then no invented dependency edges or misleading cross-cluster relationship
    And no inferred/cross-cluster edge appears without authoritative evidence
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

