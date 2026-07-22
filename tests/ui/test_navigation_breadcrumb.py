from app.common.navigation import build_navigation_breadcrumb


def labels(endpoint: str, path: str = "") -> list[str]:
    return [item["label"] for item in build_navigation_breadcrumb(endpoint, path)]


def test_integrations_and_cluster_routes_reference_integrations_menu():
    assert labels("integrations.prometheus") == ["Integrations", "Prometheus"]
    assert labels("prometheus.new_instance") == ["Integrations", "Prometheus", "Register Connection"]
    assert labels("integrations.kubernetes") == ["Integrations", "Kubernetes"]
    assert labels("cluster.add_cluster") == ["Integrations", "Kubernetes", "Add Cluster"]


def test_kubernetes_workspaces_reference_exact_sidebar_main_menu():
    assert labels("inventory.pods") == ["K8s Inventory", "Pods"]
    assert labels("analytics.forecast") == ["K8s Analytics", "Resource Forecast"]
    assert labels("kubernetes_operations.secret_management") == ["K8s Operations", "Secret Management"]
    assert labels("governance.tls_certificates") == ["K8s Governance", "TLS Certificates"]


def test_access_routes_reference_access_menu():
    assert labels("users.index") == ["Access", "User Management"]
    assert labels("users.create") == ["Access", "User Management", "Add User"]
    assert labels("settings.roles") == ["Access", "Roles & Access"]
    assert labels("notifications.activity_log") == ["Access", "Activity Audit Log"]


def test_settings_and_jobs_reference_their_sidebar_entry():
    assert labels("settings.general") == ["Settings", "General"]
    assert labels("settings.data_lifecycle.index") == ["Settings", "Data Lifecycle"]
    assert labels("integrations.jobs") == ["Jobs & Executions"]


def test_unknown_endpoint_never_uses_legacy_workspace_label():
    assert labels("unknown.endpoint") == ["KAORI"]
