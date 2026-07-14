from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, render_template, request, url_for
from flask_login import current_user, login_required

from app.cluster.onboarding import has_registered_clusters
from app.dashboard.service import get_dashboard_overview
from app.rbac.decorators import permission_required

dashboard_bp = Blueprint('dashboard', __name__)

_DASHBOARD_SECTION_TEMPLATES = {
    'kpi_cards': 'dashboard/partials/_kpi_cards.html',
    'cluster_health': 'dashboard/partials/_cluster_health.html',
    'capacity_snapshot': 'dashboard/partials/_capacity_snapshot.html',
    'alerts_summary': 'dashboard/partials/_alerts_summary.html',
    'top_consumers': 'dashboard/partials/_top_consumers.html',
    'forecast_risk': 'dashboard/partials/_forecast_risk.html',
    'data_freshness': 'dashboard/partials/_data_freshness.html',
    'recommended_actions': 'dashboard/partials/_recommended_actions.html',
}

_DASHBOARD_SECTION_LIVE_MAP = {
    'kpi_cards': {'kpi_cards'},
    'cluster_health': {'cluster_health'},
    'capacity_snapshot': {'capacity_snapshot'},
    'alerts_summary': {'alerts_summary'},
    'top_consumers': {'top_consumers'},
    'forecast_risk': {'forecast_risk'},
    'data_freshness': {'data_freshness'},
    'recommended_actions': {'recommended_actions'},
}

# Welcome is an authenticated baseline page. Each shortcut resolves to the first
# destination that the signed-in user can actually open, so restricted modules
# are omitted instead of being rendered as disabled cards.
_WELCOME_SHORTCUT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        'title': 'Kubernetes Operations Dashboard',
        'label': 'Command center',
        'description': (
            'Review cluster health, capacity risk, alerts, top consumers, '
            'reporting readiness, and prioritized actions.'
        ),
        'icon': 'layout-dashboard',
        'asset': 'Kubernetes',
        'targets': (('dashboard.view', 'dashboard.index'),),
    },
    {
        'title': 'Kubernetes Cluster',
        'label': 'Connection & sync',
        'description': (
            'Review registered clusters, connectivity, inventory synchronization, '
            'and integration readiness.'
        ),
        'icon': 'server-cog',
        'asset': 'Kubernetes',
        'targets': (('clusters.view', 'cluster.list_clusters'),),
    },
    {
        'title': 'Kubernetes Inventory',
        'label': 'Asset visibility',
        'description': (
            'Explore clusters, nodes, namespaces, workloads, Pods, services, '
            'ingress, storage, and configuration relationships.'
        ),
        'icon': 'boxes',
        'asset': 'Kubernetes',
        'targets': (('inventory.view', 'inventory.overview'),),
    },
    {
        'title': 'Kubernetes Analytics',
        'label': 'Analytics',
        'description': (
            'Analyze utilization, capacity, workload efficiency, storage, forecast '
            'risk, top consumers, alerts, and anomalies.'
        ),
        'icon': 'chart-column',
        'asset': 'Kubernetes',
        'targets': (('analytics.view', 'analytics.overview'),),
    },
    {
        'title': 'Kubernetes Operations',
        'label': 'Controlled actions',
        'description': (
            'Run permission-aware operational workflows such as validated Secret '
            'management and TLS rotation.'
        ),
        'icon': 'wrench',
        'asset': 'Kubernetes',
        'targets': (('kubernetes_secrets.view', 'kubernetes_operations.secret_management'),),
    },
    {
        'title': 'Intelligence',
        'label': 'Recommendations',
        'description': (
            'Review contextual recommendations, alert intelligence, rule definitions, '
            'impacted assets, and remediation guidance.'
        ),
        'icon': 'brain-circuit',
        'asset': 'Cross-domain',
        'targets': (('intelligence.view', 'intelligence.recommendations'),),
    },
    {
        'title': 'Governance',
        'label': 'Policy & lifecycle',
        'description': (
            'Review infrastructure governance posture, beginning with Kubernetes TLS '
            'certificate inventory and lifecycle controls.'
        ),
        'icon': 'shield-check',
        'asset': 'Cross-domain',
        'targets': (
            ('governance.view', 'governance.overview'),
            ('tls_certificates.view', 'governance.tls_certificates'),
        ),
    },
    {
        'title': 'Reports',
        'label': 'Management output',
        'description': (
            'Open operational reports, generated artifacts, templates, schedules, '
            'and storage workflows available to your role.'
        ),
        'icon': 'file-text',
        'asset': 'Cross-domain',
        'targets': (
            ('reports.view', 'reports.overview'),
            ('reports.generate', 'reports.generate_report'),
            ('reports.manage_templates', 'reports.report_templates'),
            ('reports.manage_schedules', 'reports.schedules'),
            ('reports.manage_storage', 'reports.storage'),
        ),
    },
    {
        'title': 'Access Management',
        'label': 'Administration',
        'description': (
            'Manage users, roles, permissions, login activity, or operational audit '
            'records according to assigned authority.'
        ),
        'icon': 'users-round',
        'asset': 'Platform',
        'targets': (
            ('users.view', 'settings.users'),
            ('roles.view', 'settings.roles'),
            ('settings.view_login_activity', 'settings.login_activity'),
            ('settings.view_operational_activity', 'notifications.activity_log'),
        ),
    },
    {
        'title': 'Account & Settings',
        'label': 'Personal workspace',
        'description': (
            'Manage your account and time preferences; elevated roles can also '
            'configure integrations and system settings.'
        ),
        'icon': 'settings-2',
        'asset': 'Platform',
        'targets': ((None, 'settings.account'),),
    },
)


def _build_welcome_shortcuts() -> list[dict[str, str]]:
    shortcuts: list[dict[str, str]] = []

    for definition in _WELCOME_SHORTCUT_DEFINITIONS:
        resolved_endpoint: str | None = None

        for permission_key, endpoint in definition['targets']:
            if permission_key is None or current_user.has_permission(permission_key):
                resolved_endpoint = endpoint
                break

        if resolved_endpoint is None:
            continue

        shortcuts.append(
            {
                'title': definition['title'],
                'label': definition['label'],
                'description': definition['description'],
                'icon': definition['icon'],
                'asset': definition['asset'],
                'href': url_for(resolved_endpoint),
            }
        )

    return shortcuts


@dashboard_bp.before_request
def block_clusterless_dashboard_sections():
    """Keep lazy dashboard sections aligned with the full-page cluster blocker."""
    if request.endpoint != 'dashboard.section':
        return None

    if has_registered_clusters() is False:
        return render_template('components/cluster/_onboarding_banner.html')

    return None


@dashboard_bp.route('/welcome')
@login_required
def welcome():
    shortcuts = _build_welcome_shortcuts()

    return render_template(
        'dashboard/welcome.html',
        shortcuts=shortcuts,
        shortcut_count=len(shortcuts),
    )


@dashboard_bp.route('/')
@permission_required('dashboard.view')
def index():
    selected_cluster_id = request.args.get('cluster_id') or None
    cluster_health_page = request.args.get('cluster_health_page', '1')

    dashboard = get_dashboard_overview(
        selected_cluster_id=selected_cluster_id,
        cluster_health_page=cluster_health_page,
        hydrate_live_sections=False,
    )

    template_name = 'dashboard/partials/_content.html' if request.headers.get('HX-Request') else 'dashboard/index.html'

    return render_template(
        template_name,
        dashboard=dashboard,
    )


@dashboard_bp.route('/dashboard/section/<string:section>')
@permission_required('dashboard.view')
def section(section: str):
    template_name = _DASHBOARD_SECTION_TEMPLATES.get(section)
    if template_name is None:
        abort(404)

    selected_cluster_id = request.args.get('cluster_id') or None
    cluster_health_page = request.args.get('cluster_health_page', '1')

    dashboard = get_dashboard_overview(
        selected_cluster_id=selected_cluster_id,
        cluster_health_page=cluster_health_page,
        hydrate_live_sections=True,
        live_sections=_DASHBOARD_SECTION_LIVE_MAP.get(section, {section}),
    )

    return render_template(
        template_name,
        dashboard=dashboard,
    )
