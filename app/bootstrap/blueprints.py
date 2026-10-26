from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Import and register KAORI web domains after extensions are initialized."""
    from app.access import bp as access_bp
    from app.access.authentication.routes import auth_bp
    from app.access.identity_providers.routes import bp as identity_providers_bp
    from app.access.users.routes import bp as users_bp
    from app.analytics.routes import analytics_bp
    from app.artifact_registry.routes import artifact_registry_bp
    from app.integrations.delivery.notification_channels.routes import notification_channels_bp
    from app.integrations.observability.alert_source.providers.alertmanager.application.routes import alertmanager_bp
    from app.integrations.observability.metrics_source.application.routes import metrics_bp
    from app.integrations.registry.providers.harbor.application.routes import harbor_bp
    from app.integrations.secrets_management.secrets_pki.providers.vault.application.routes import vault_bp
    from app.integrations.source_control.source_control.providers.github.application.routes import github_source_bp
    from app.integrations.source_control.source_control.providers.github.application.uat_routes import github_uat_bp
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
    from app.kubernetes.operations.secrets.approval_inbox import (
        get_secret_reveal_approval_work_inbox,
        get_secret_reveal_requester_work_inbox,
    )
    from app.kubernetes.tenant.approval_inbox import get_tenant_release_work_inbox
    from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
    from app.kubernetes.tenant.capsule_rbac_bootstrap import (
        bootstrap_missing_capsule_roles,
        check_capsule_role_bootstrap,
        latest_capsule_role_bootstrap_evidence,
    )
    from app.kubernetes.tenant.native_handoff_dry_run import _read_resource
    from app.kubernetes.tenant.native_handoff_executor import (
        latest_native_handoff_execution,
        native_handoff_execution_history,
    )
    from app.kubernetes.tenant.native_handoff_readback import (
        _latest_native_dry_run,
        native_handoff_readback_history,
        verify_external_native_component,
    )
    from app.kubernetes.tenant.native_handoff_recovery import readback_proves_handoff_not_started
    from app.kubernetes.tenant.native_no_transfer_recovery import (
        _source_history,
        _verify_original_provider_state,
        require_authorized_no_transfer_restart,
    )
    from app.kubernetes.tenant.native_successor_acceptance import latest_native_successor_acceptance
    from app.kubernetes.tenant.release_handoff_approval import (
        _plan_hash,
        latest_release_handoff_approval,
        latest_release_handoff_plan,
    )
    from app.kubernetes.tenant.routes import tenant_bp
    from app.platform_operations import bp as platform_operations_bp
    from app.platform_operations.health import health_bp
    from app.platform_operations.jobs.routes import bp as jobs_bp
    from app.platform_operations.notifications.routes import notifications_bp
    from app.reports.routes import reports_bp
    from app.secrets_pki.routes import secrets_pki_bp
    from app.security_posture.routes import security_posture_bp
    from app.source_control.routes import source_control_bp
    from app.settings import bp as settings_bp
    from app.storage.object_storage.dashboard.routes import object_storage_dashboard_bp
    from app.storage.object_storage.inventory.routes import object_storage_inventory_bp
    from app.welcome.routes import welcome_bp

    # Compose the Tenant-owned committed approval projection into the shared
    # Notification Work Inbox once per Flask app; no global mutable registry.
    app.extensions['kaori_tenant_approval_work_inbox'] = get_tenant_release_work_inbox
    # Project Kubernetes-owned committed Secret Reveal approvals without
    # importing Kubernetes services into Notifications.
    app.extensions['kaori_secret_reveal_approval_work_inbox'] = get_secret_reveal_approval_work_inbox
    # Independently present approved requester-owned work from committed requests.
    app.extensions['kaori_secret_reveal_requester_work_inbox'] = get_secret_reveal_requester_work_inbox
    # Integration presentation invokes Tenant-owned cluster RBAC operations.
    # Keep this wiring application-scoped to prevent reverse domain imports.
    app.extensions['kaori_tenant_capsule_rbac_bootstrap'] = {
        'bootstrap_missing_capsule_roles': bootstrap_missing_capsule_roles,
        'check_capsule_role_bootstrap': check_capsule_role_bootstrap,
        'latest_capsule_role_bootstrap_evidence': latest_capsule_role_bootstrap_evidence,
    }

    # Compose canonical Tenant handoff evidence producers once per Flask app.
    # Approval and preflight consume them without circular imports or implicit
    # provider actions; unchanged Tenant services enforce the same safeguards.
    app.extensions['kaori_tenant_handoff_operations'] = {
        'build_capsule_handoff_worklist': build_capsule_handoff_worklist,
        'native_handoff_execution_history': native_handoff_execution_history,
        'native_handoff_readback_history': native_handoff_readback_history,
        'readback_proves_handoff_not_started': readback_proves_handoff_not_started,
        '_source_history': _source_history,
        '_verify_original_provider_state': _verify_original_provider_state,
        'require_authorized_no_transfer_restart': require_authorized_no_transfer_restart,
        '_read_resource': _read_resource,
        'latest_native_handoff_execution': latest_native_handoff_execution,
        '_latest_native_dry_run': _latest_native_dry_run,
        'verify_external_native_component': verify_external_native_component,
        'latest_native_successor_acceptance': latest_native_successor_acceptance,
        '_plan_hash': _plan_hash,
        'latest_release_handoff_approval': latest_release_handoff_approval,
        'latest_release_handoff_plan': latest_release_handoff_plan,
    }

    for blueprint in (
        auth_bp,
        access_bp,
        artifact_registry_bp,
        source_control_bp,
        security_posture_bp,
        secrets_pki_bp,
        welcome_bp,
        kubernetes_dashboard_bp,
        object_storage_dashboard_bp,
        cluster_bp,
        inventory_bp,
        object_storage_inventory_bp,
        notifications_bp,
        notification_channels_bp,
        alert_intelligence_bp,
        analytics_bp,
        governance_bp,
        kubernetes_operations_bp,
        tenant_bp,
        health_bp,
        identity_providers_bp,
        intelligence_bp,
        automation_control_bp,
        integrations_bp,
        jobs_bp,
        platform_operations_bp,
        reports_bp,
        metrics_bp,
        harbor_bp,
        vault_bp,
        github_source_bp,
        github_uat_bp,
        minio_bp,
        settings_bp,
        users_bp,
        alertmanager_bp,
    ):
        app.register_blueprint(blueprint)
