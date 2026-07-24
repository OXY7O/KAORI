from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Import and register KAORI web domains after extensions are initialized."""
    from app.alertmanager.routes import alertmanager_bp
    from app.analytics.routes import analytics_bp
    from app.auth.routes import auth_bp
    from app.automation_control.routes import automation_control_bp
    from app.cluster.routes import cluster_bp
    from app.dashboards.kubernetes.routes import kubernetes_dashboard_bp
    from app.governance.routes import governance_bp
    from app.health import health_bp
    from app.integrations.routes import integrations_bp
    from app.intelligence.routes import intelligence_bp
    from app.jobs.routes import bp as jobs_bp
    from app.inventory.routes import inventory_bp
    from app.kubernetes_operations.routes import kubernetes_operations_bp
    from app.notifications.routes import notifications_bp
    from app.prometheus.routes import prometheus_bp
    from app.reports.routes import reports_bp
    from app.settings import bp as settings_bp
    from app.users.routes import bp as users_bp
    from app.welcome.routes import welcome_bp

    for blueprint in (
        auth_bp,
        welcome_bp,
        kubernetes_dashboard_bp,
        cluster_bp,
        inventory_bp,
        notifications_bp,
        analytics_bp,
        governance_bp,
        kubernetes_operations_bp,
        health_bp,
        intelligence_bp,
        automation_control_bp,
        integrations_bp,
        jobs_bp,
        reports_bp,
        prometheus_bp,
        settings_bp,
        users_bp,
        alertmanager_bp,
    ):
        app.register_blueprint(blueprint)
