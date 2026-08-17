from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Import and register KAORI web domains after extensions are initialized."""
    from app.access import bp as access_bp
    from app.access.authentication.routes import auth_bp
    from app.access.identity_providers.routes import bp as identity_providers_bp
    from app.access.users.routes import bp as users_bp
    from app.analytics.routes import analytics_bp
    from app.integrations.delivery.notification_channels.routes import notification_channels_bp
    from app.integrations.observability.alert_source.providers.alertmanager.application.routes import alertmanager_bp
    from app.integrations.observability.metrics_source.application.routes import metrics_bp
    from app.integrations.routes import integrations_bp
    from app.integrations.storage.object_storage.providers.minio.application.routes import minio_bp
    from app.intelligence.alert_intelligence.routes import alert_intelligence_bp
    from app.intelligence.automation_control.routes import automation_control_bp
    from app.intelligence.routes import intelligence_bp
    from app.kubernetes.cluster.routes import cluster_bp
    from app.kubernetes.dashboard.routes import kubernetes_dashboard_bp
    from app.kubernetes.governance.routes import governance_bp
    from app.kubernetes.inventory.routes import inventory_bp
    from app.kubernetes.operations.routes import kubernetes_operations_bp
    from app.platform_operations import bp as platform_operations_bp
    from app.platform_operations.health import health_bp
    from app.platform_operations.jobs.routes import bp as jobs_bp
    from app.platform_operations.notifications.routes import notifications_bp
    from app.reports.routes import reports_bp
    from app.settings import bp as settings_bp
    from app.storage.object_storage.inventory.routes import object_storage_inventory_bp
    from app.welcome.routes import welcome_bp

    for blueprint in (
        auth_bp,
        access_bp,
        welcome_bp,
        kubernetes_dashboard_bp,
        cluster_bp,
        inventory_bp,
        object_storage_inventory_bp,
        notifications_bp,
        notification_channels_bp,
        alert_intelligence_bp,
        analytics_bp,
        governance_bp,
        kubernetes_operations_bp,
        health_bp,
        identity_providers_bp,
        intelligence_bp,
        automation_control_bp,
        integrations_bp,
        jobs_bp,
        platform_operations_bp,
        reports_bp,
        metrics_bp,
        minio_bp,
        settings_bp,
        users_bp,
        alertmanager_bp,
    ):
        app.register_blueprint(blueprint)
