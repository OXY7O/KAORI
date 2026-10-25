"""SC-03 opt-in GitHub UAT must never expose cross-installation data to users."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.exceptions import Forbidden, NotFound

from app.integrations.source_control import uat_access
from app.integrations.source_control.source_control.providers.github import kernel_contract


def _actor(*, admin=True, source='database', permitted=True):
    return SimpleNamespace(
        is_authenticated=True,
        is_active=True,
        is_super_admin=admin,
        auth_source=source,
        has_permission=lambda _: permitted,
    )


def test_available_provider_needs_no_uat_env_flag(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        uat_access,
        'provider_kind',
        lambda *_: SimpleNamespace(available=True),
    )
    with app.app_context():
        assert uat_access.uat_enabled()


def test_planned_provider_blocks_uat(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        uat_access,
        'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    with app.app_context():
        assert not uat_access.uat_enabled()


@pytest.mark.parametrize(
    'user',
    [
        _actor(admin=False),
        _actor(source='sso'),
        _actor(permitted=False),
        SimpleNamespace(is_authenticated=False, is_super_admin=True, auth_source='database'),
    ],
)
def test_only_local_authorized_super_admin_can_access_uat(user):
    assert not uat_access.local_super_admin(user)


def test_fails_closed_before_resource_discovery(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        uat_access,
        'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    with app.app_context():
        with pytest.raises(NotFound):
            uat_access.require_uat_access()


def test_fails_closed_for_non_admin_when_enabled(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        uat_access,
        'provider_kind',
        lambda *_: SimpleNamespace(available=True),
    )
    monkeypatch.setattr(uat_access, 'current_user', _actor(admin=False))
    with app.app_context():
        with pytest.raises(Forbidden):
            uat_access.require_uat_access()


def test_uat_routes_are_isolated_and_do_not_call_github_during_get():
    root = Path(__file__).resolve().parents[2]
    file = root / ('app/integrations/source_control/source_control/providers/github/application/uat_routes.py')
    source = file.read_text()
    assert "url_prefix='/integrations/source-control/github/uat'" in source
    assert 'require_uat_access()' in source
    assert 'read_installation_inventory(' in source
    assert 'enqueue_github_app_job(' in source
    assert 'enqueue_source_repository_sync(' in source
    assert "@permission_required('integrations.manage')" in source
    assert 'FlaskForm().validate_on_submit()' in source
    assert "trigger_type='uat'" in source
    assert 'GitHubAppClient' not in source
    assert 'requests.get(' not in source
    assert 'current_user.is_super_admin' not in source


def test_uat_templates_keep_committed_unknown_vs_zero_and_htmx_pagination():
    root = Path(__file__).resolve().parents[2]
    prefix = root / 'app/templates/integrations/source_control/github'
    inventory = (prefix / '_inventory_table.html').read_text()
    detail = (prefix / 'uat_detail.html').read_text()
    assert 'inventory.total is none' in inventory
    assert 'inventory.total == 0' in inventory
    assert 'hx-target="#source-control-inventory"' in inventory
    assert '[5, 10, 25, 50]' in inventory
    assert 'hx-trigger="every 15s"' in inventory
    assert 'exact_default_branch_sha' in inventory
    assert 'revision_observed_at' in inventory
    assert 'action_form.hidden_tag()' in detail
    assert 'integrations/components/_workspace.html' in detail
    assert '<style' not in inventory and '<style' not in detail


def test_live_registration_is_restricted_before_credentials_are_read():
    root = Path(__file__).resolve().parents[2]
    source = root.joinpath(
        'app/integrations/source_control/source_control/providers/github/application/routes.py'
    ).read_text()
    view = source.split('def new_connection()')[1].split('@github_source_bp.post')[0]
    assert 'if available:' in view
    assert 'require_uat_access()' in view
    assert view.index('require_uat_access()') < view.index('form = GitHubAppConnectionForm()')


def test_github_uat_detail_exposes_only_committed_delivery_job_links():
    root = Path(__file__).resolve().parents[2]
    routes = root.joinpath(
        'app/integrations/source_control/source_control/providers/github/application/uat_routes.py'
    ).read_text()
    detail = root.joinpath('app/templates/integrations/source_control/github/uat_detail.html').read_text()
    assert 'filter_by(installation_id=installation.id)' in routes
    assert 'SourceWebhookDelivery.received_at.desc()' in routes
    assert 'delivery.dispatched_job_execution_id' in detail
    assert 'delivery.processing_state' in detail
    assert 'delivery.payload_sha256' not in detail
    assert 'delivery.repository_native_id_hint' not in detail
    assert 'integrations/components/_provider_detail_posture.html' in detail
    assert 'provider_detail_posture.render(' in detail
    assert 'components/framed_workspace_tabs.html' in detail
    assert 'framed_workspace_tabs.render(' in detail


@pytest.mark.parametrize(
    ('admin', 'expected'),
    [
        (True, '/integrations/source-control/github/uat/installations/321'),
        (False, '/integrations/source-control/github/'),
    ],
)
def test_github_provider_open_resolves_record_scoped_detail_without_bypassing_uat(monkeypatch, admin, expected):
    app = Flask(__name__)
    app.add_url_rule(
        '/integrations/source-control/github/uat/installations/<int:installation_id>',
        endpoint='github_source_uat.detail',
        view_func=lambda installation_id: str(installation_id),
    )
    app.add_url_rule(
        '/integrations/source-control/github/',
        endpoint='github_source.index',
        view_func=lambda: 'GitHub Integrations',
    )
    monkeypatch.setattr(kernel_contract, 'current_user', _actor(admin=admin))
    with app.test_request_context('/integrations/source-control'):
        assert kernel_contract._detail_url(SimpleNamespace(id=321), '') == expected


def test_github_manage_detail_uses_existing_provider_tabs_without_exposing_secrets():
    root = Path(__file__).resolve().parents[2]
    detail = (root / 'app/templates/integrations/source_control/github/uat_detail.html').read_text()
    kernel = (root / 'app/integrations/source_control/source_control/providers/github/kernel_contract.py').read_text()

    provider_rows = (root / 'app/templates/integrations/partials/_domain_workspace.html').read_text()
    domain_service = (root / 'app/integrations/domain_service.py').read_text()
    assert 'row.detail_url or url_for(row.workspace_endpoint)' in provider_rows
    assert 'module.detail_url_for_record(record, section=' in domain_service
    assert "url_for('github_source_uat.detail', installation_id=record.id)" in kernel
    assert 'local_super_admin(current_user)' in kernel
    assert "return url_for('github_source.index')" in kernel
    for title in ('Configuration', 'Validation & Capabilities', 'Runtime & History', 'Inventory & Lifecycle'):
        assert title in detail
    assert "integrationWorkspaceTabs(['configuration', 'validation', 'runtime', 'inventory']" in detail
    assert 'provider_detail_posture.render(' in detail
    assert 'framed_workspace_tabs.render(' in detail
    assert 'url_for("github_source.index", tab="registry")' in detail
    assert 'GitHub Full Validation' in detail
    assert 'action_form.hidden_tag()' in detail
    assert "url_for('github_source_uat.validate', installation_id=installation.id)" in detail
    assert "url_for('github_source_uat.synchronize', installation_id=installation.id)" in detail
    assert "readiness != 'ready'" in detail
    assert 'integrations/source_control/github/_inventory_table.html' in detail
    assert 'delivery.dispatched_job_execution_id' in detail
    assert 'delivery.processing_state' in detail
    assert 'canonical.environment' in detail
    assert 'installation.native_installation_id' in detail
    assert 'form.private_key_pem' not in detail
    assert 'form.webhook_secret' not in detail
    assert 'credential.private_key' not in detail


def test_github_configuration_reuses_approved_connection_contract_and_operational_context() -> None:
    root = Path(__file__).resolve().parents[2]
    detail = (root / 'app/templates/integrations/source_control/github/uat_detail.html').read_text()
    kubernetes = (
        root
        / 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_connection_contract.html'
    ).read_text()
    shared = (root / 'app/templates/integrations/components/_provider_operational_context.html').read_text()

    assert '"Committed grants only"' in detail
    assert 'Committed evidence, not installation selection' not in detail
    assert 'data-kaori-connection-contract-v2' in detail
    assert 'data-kaori-connection-summary' in detail
    assert 'data-kaori-connection-evidence' in detail
    assert "ui.section_header('file-key-2'," in detail
    assert 'action_html=github_connection_status' in detail
    assert 'xl:grid-cols-4' in detail
    assert 'lg:grid-cols-[minmax(20rem,1.4fr)_repeat(3,minmax(12rem,0.75fr))]' in detail
    assert "ui.palette_icon('waypoints', 'brand', size='sm')" in detail
    assert "table_label.metadata_label('GitHub REST API v3', 'git-branch')" in detail
    assert 'operational_context.render(' in detail
    assert "('Synchronize', 'Commit repository grants" in detail
    assert 'installation.native_app_id' in detail
    assert 'installation.native_installation_id' in detail
    assert 'installation.repository_scope|title' in detail
    assert "inventory.total is not none else 'Not Observed'" in detail
    assert "integration_status(readiness, display='indicator')" in detail
    assert 'integrations/components/_provider_operational_context.html' in detail
    assert 'operational_context.render(' in kubernetes
    assert 'data-kaori-provider-operational-context' in shared
    assert '<style' not in detail


def test_github_minimum_validation_permissions_reuse_kubernetes_modal_family() -> None:
    root = Path(__file__).resolve().parents[2]
    detail = (root / 'app/templates/integrations/source_control/github/uat_detail.html').read_text()
    github = (
        root
        / 'app/templates/integrations/source_control/github/partials/_minimum_validation_permissions.html'
    ).read_text()
    kubernetes = (
        root
        / 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_minimum_validation_rbac.html'
    ).read_text()
    readiness = (
        root / 'app/integrations/source_control/source_control/providers/github/readiness.py'
    ).read_text()

    assert "partials/_minimum_validation_permissions.html" in detail
    assert 'data-kaori-github-minimum-validation-permissions' in github
    assert 'data-kaori-github-permission-modal' in github
    assert 'components/workspace_tabs.html' in github
    assert 'components/workspace_tabs.html' in kubernetes
    assert "prefix='github-minimum-permissions'" in github
    assert "('baseline', 'Baseline Validation Permissions', 'shield-check')" in github
    assert "('governance', 'Optional Governance Permissions', 'key-round')" in github
    assert "copyText('baselinePermissions', 'baseline')" in github
    assert "copyText('governancePermissions', 'governance')" in github
    assert 'aria-modal="true"' in github
    assert 'aria-labelledby="github-minimum-permissions-title"' in github
    assert 'closeModal()' in github
    assert 'navigator.clipboard?.writeText' in github
    assert '"metadata": "read"' in github
    assert '"contents": "read"' in github
    for capability in ('pull_requests', 'actions', 'checks', 'deployments'):
        assert f'"{capability}": "read"' in github
        assert f"'{capability}'" in readiness
    assert "'source_revision': frozenset({'metadata', 'contents'})" in readiness
    assert '"administration": "write"' not in github
    assert '"secrets": "read"' not in github
    assert 'form.private_key_pem' not in github
    assert 'form.webhook_secret' not in github
    assert 'https://github.com/settings/installations' in detail
    assert 'rel="noopener noreferrer"' in detail
    assert 'Configure Connection' in detail
    assert "url_for('github_source.new_connection')" not in detail
    assert "url_for('github_source_uat.validate', installation_id=installation.id)" in detail
    assert 'GitHub permission changes require fresh Full Validation' in detail
