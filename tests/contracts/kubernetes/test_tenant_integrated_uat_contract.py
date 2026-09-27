from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_workspace_keeps_one_sidebar_destination_and_internal_surfaces() -> None:
    menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    tabs = (ROOT / 'app/templates/kubernetes/tenant/workspace_tabs.html').read_text(encoding='utf-8')

    assert '>Tenant</span>' in menu
    assert 'tenant.management' not in menu
    assert 'tenant.inventory' not in menu
    assert 'tenant.analytics' not in menu

    assert "@tenant_bp.get('/management')" in routes
    assert "@tenant_bp.get('/inventory')" in routes
    assert "@tenant_bp.get('/analytics')" in routes
    assert "url_for('tenant.management')" in tabs
    assert "url_for('tenant.inventory')" in tabs
    assert "url_for('tenant.analytics')" in tabs
    assert 'Management' in tabs
    assert 'Inventory' in tabs
    assert 'Analytics' in tabs


def test_tenant_workspace_reads_committed_cross_child_state() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')

    for model_name in (
        'TenantCredential',
        'TenantManagedResourceIntent',
        'TenantDomainReservation',
        'TenantExposurePolicy',
        'TenantAuditEvidence',
        'TenantAdvancedCapabilityIntent',
    ):
        assert model_name in workspace

    assert "get_active_recommendation_findings(domain='kubernetes')" in workspace
    assert "startswith('kubernetes.tenant.')" in workspace


def test_tenant_management_exposes_governed_credential_lifecycle_without_secret_material() -> None:
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/management.html').read_text(encoding='utf-8')

    for path in (
        '/credentials/<int:credential_id>/renew',
        '/credentials/<int:credential_id>/suspend',
        '/credentials/<int:credential_id>/resume',
        '/credentials/<int:credential_id>/revoke',
    ):
        assert f"@tenant_bp.post('{path}')" in routes

    assert 'service_account_name' in template
    assert 'renewal_due_at' in template
    assert 'valid_until' in template
    assert 'credential.token' not in template
    assert 'credential.token' not in template
    assert 'credential.kubeconfig' not in template


def test_tenant_inventory_and_analytics_keep_provider_and_evidence_states_explicit() -> None:
    inventory = (ROOT / 'app/templates/kubernetes/tenant/inventory.html').read_text(encoding='utf-8')
    analytics = (ROOT / 'app/templates/kubernetes/tenant/analytics.html').read_text(encoding='utf-8')

    assert 'provider_state' in inventory
    assert 'reconciliation_authority' in inventory
    assert 'correlation_status' in inventory
    assert 'Unknown' in analytics
    assert 'Tenant Governance' in analytics
    assert 'Reports' in analytics
