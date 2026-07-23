"""Canonical navigation context for the KAORI topbar breadcrumb.

The first breadcrumb item after KAORI must match the visible main-menu label in
KAORI's sidebar. Child labels describe the selected submenu or workflow page.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class BreadcrumbItem:
    label: str
    icon: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"label": self.label, "icon": self.icon}


_ENDPOINT_LABELS: dict[str, str] = {
    # Inventory
    "inventory.overview": "Overview",
    "inventory.topology": "Topology",
    "inventory.nodes": "Nodes",
    "inventory.namespaces": "Namespaces",
    "inventory.workloads": "Workloads",
    "inventory.pods": "Pods",
    "inventory.services": "Services",
    "inventory.ingresses": "Ingresses",
    "inventory.storage": "Storage",
    "inventory.configuration": "Configuration",
    # Analytics
    "analytics.overview": "Overview",
    "analytics.utilization": "Resource Utilization",
    "analytics.capacity": "Capacity Analysis",
    "analytics.storage": "Storage Analysis",
    "analytics.workload": "Workload Analysis",
    "analytics.forecast": "Resource Forecast",
    "analytics.top_consumers": "Top Consumers",
    "analytics.alerts": "Alerts & Anomalies",
    # Intelligence
    "intelligence.index": "Recommendations",
    "intelligence.recommendations": "Recommendations",
    "intelligence.alert_intelligence": "Alert Intelligence",
    "intelligence.catalog": "Catalog",
    # Reports
    "reports.overview": "Overview",
    "reports.generate_report": "Generate",
    "reports.generated_reports": "Generated",
    "reports.report_templates": "Templates",
    "reports.schedules": "Schedules",
    "reports.storage": "Storage",
    # Kubernetes operations and governance
    "kubernetes_operations.configmap_management": "ConfigMap Management",
    "kubernetes_operations.secret_management": "Secret Management",
    "governance.overview": "Overview",
    "governance.tls_certificates": "TLS Certificates",
    # Settings
    "settings.general": "General",
    "settings.account": "Account",
    "settings.reports": "Report Settings",
    "settings.data_lifecycle.index": "Data Lifecycle",
    "settings.secret_reveal.index": "Secret Reveal",
    # Access
    "users.index": "User Management",
    "settings.roles": "Roles & Access",
    "settings.permission_catalog": "Permission Catalog",
    "notifications.activity_log": "Activity Audit Log",
}

_WORKFLOW_LABELS: tuple[tuple[str, str], ...] = (
    ("cluster.add_cluster", "Add Cluster"),
    ("cluster.edit_cluster", "Edit Cluster"),
    ("prometheus.new_instance", "Register Connection"),
    ("prometheus.instance_detail", "Connection Details"),
    ("alertmanager.new_instance", "Register Connection"),
    ("alertmanager.instance_detail", "Connection Details"),
    ("integrations.bind_prometheus_source", "Scope Binding"),
    ("integrations.bind_alertmanager_source", "Scope Binding"),
    ("users.create", "Add User"),
    ("users.edit", "Edit User"),
    ("users.reset_password", "Reset Password"),
    ("users.providers", "Identity Providers"),
    ("users.create_provider", "Add Provider"),
    ("users.edit_provider", "Edit Provider"),
    ("users.external_identities", "External Identities"),
    ("settings.new_role", "Add Role"),
    ("settings.clone_role", "Clone Role"),
    ("settings.role_detail", "Role Details"),
    ("settings.edit_role", "Edit Role"),
)


def _items(*items: BreadcrumbItem) -> list[dict[str, str | None]]:
    return [item.as_dict() for item in items]


def _leaf(endpoint: str, fallback: str) -> str:
    return _ENDPOINT_LABELS.get(endpoint, fallback)


def _append_workflow(items: list[BreadcrumbItem], endpoint: str) -> list[BreadcrumbItem]:
    workflow = next((label for candidate, label in _WORKFLOW_LABELS if candidate == endpoint), None)
    if workflow and workflow != items[-1].label:
        items.append(BreadcrumbItem(workflow))
    return items


def _deduplicate(items: Iterable[BreadcrumbItem]) -> list[BreadcrumbItem]:
    result: list[BreadcrumbItem] = []
    for item in items:
        if not result or result[-1].label != item.label:
            result.append(item)
    return result


def build_navigation_breadcrumb(endpoint: str | None, path: str = "") -> list[dict[str, str | None]]:
    """Return breadcrumb items whose root matches the KAORI sidebar main menu."""

    endpoint = endpoint or ""

    if endpoint == "welcome.index":
        items = [BreadcrumbItem("Welcome", "sparkles")]
    elif endpoint.startswith("kubernetes_dashboard."):
        items = [
            BreadcrumbItem("Dashboards", "layout-dashboard"),
            BreadcrumbItem("Kubernetes Operations"),
        ]
    elif endpoint.startswith("cluster.") or endpoint.startswith("integrations.kubernetes"):
        items = [BreadcrumbItem("Integrations", "plug"), BreadcrumbItem("Kubernetes")]
        items = _append_workflow(items, endpoint)
    elif endpoint.startswith("inventory."):
        items = [
            BreadcrumbItem("K8s Inventory", "boxes"),
            BreadcrumbItem(_leaf(endpoint, "Overview")),
        ]
    elif endpoint.startswith("kubernetes_operations."):
        fallback = "Secret Management" if "secret" in endpoint or "/secrets" in path else "ConfigMap Management"
        items = [
            BreadcrumbItem("K8s Operations", "terminal-square"),
            BreadcrumbItem(_leaf(endpoint, fallback)),
        ]
    elif endpoint.startswith("governance."):
        items = [
            BreadcrumbItem("K8s Governance", "shield-check"),
            BreadcrumbItem(_leaf(endpoint, "TLS Certificates")),
        ]
    elif endpoint.startswith("analytics."):
        items = [
            BreadcrumbItem("K8s Analytics", "bar-chart-3"),
            BreadcrumbItem(_leaf(endpoint, "Overview")),
        ]
    elif endpoint.startswith("intelligence."):
        items = [
            BreadcrumbItem("Intelligence", "brain-circuit"),
            BreadcrumbItem(_leaf(endpoint, "Recommendations")),
        ]
    elif endpoint.startswith("reports."):
        items = [BreadcrumbItem("Reports", "file-text"), BreadcrumbItem(_leaf(endpoint, "Overview"))]
    elif endpoint == "integrations.jobs" or endpoint.startswith("jobs."):
        items = [BreadcrumbItem("Jobs & Executions", "workflow")]
    elif endpoint.startswith("prometheus.") or "prometheus" in endpoint:
        items = [BreadcrumbItem("Integrations", "plug"), BreadcrumbItem("Prometheus")]
        items = _append_workflow(items, endpoint)
    elif endpoint.startswith("alertmanager.") or "alertmanager" in endpoint:
        items = [BreadcrumbItem("Integrations", "plug"), BreadcrumbItem("Alertmanager")]
        items = _append_workflow(items, endpoint)
    elif endpoint.startswith("integrations."):
        leaf = {
            "integrations.overview": "Overview",
            "integrations.kubernetes": "Kubernetes",
            "integrations.prometheus": "Prometheus",
            "integrations.alertmanager": "Alertmanager",
        }.get(endpoint, "Overview")
        items = [BreadcrumbItem("Integrations", "plug"), BreadcrumbItem(leaf)]
    elif endpoint.startswith("users."):
        items = [BreadcrumbItem("Access", "users-round"), BreadcrumbItem("User Management")]
        items = _append_workflow(items, endpoint)
    elif endpoint.startswith("notifications."):
        items = [BreadcrumbItem("Access", "users-round"), BreadcrumbItem(_leaf(endpoint, "Activity Audit Log"))]
    elif endpoint.startswith("settings.roles") or endpoint in {
        "settings.new_role",
        "settings.clone_role",
        "settings.role_detail",
        "settings.edit_role",
    }:
        items = [BreadcrumbItem("Access", "users-round"), BreadcrumbItem("Roles & Access")]
        items = _append_workflow(items, endpoint)
    elif endpoint == "settings.permission_catalog":
        items = [BreadcrumbItem("Access", "users-round"), BreadcrumbItem("Permission Catalog")]
    elif endpoint.startswith("settings."):
        items = [BreadcrumbItem("Settings", "settings-2"), BreadcrumbItem(_leaf(endpoint, "General"))]
    else:
        items = [BreadcrumbItem("KAORI", "compass")]

    return _items(*_deduplicate(items))
