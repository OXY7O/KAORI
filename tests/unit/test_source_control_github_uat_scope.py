"""SC-03 opt-in GitHub UAT must never expose cross-installation data to users."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.exceptions import Forbidden, NotFound

from app.integrations.source_control import uat_access


def _actor(*, admin=True, source='database', permitted=True):
    return SimpleNamespace(
        is_authenticated=True, is_active=True, is_super_admin=admin,
        auth_source=source, has_permission=lambda _: permitted,
    )


def test_uat_disabled_without_flag(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        uat_access, 'provider_kind',
        lambda *_: SimpleNamespace(available=True),
    )
    app.config['SOURCE_CONTROL_GITHUB_UAT_ENABLED'] = False
    with app.app_context():
        assert not uat_access.uat_enabled()


def test_provider_planned_disables_uat_even_with_flag(monkeypatch):
    app = Flask(__name__)
    app.config['SOURCE_CONTROL_GITHUB_UAT_ENABLED'] = True
    monkeypatch.setattr(
        uat_access, 'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    with app.app_context():
        assert not uat_access.uat_enabled()


@pytest.mark.parametrize('user', [
    _actor(admin=False), _actor(source='sso'), _actor(permitted=False),
    SimpleNamespace(is_authenticated=False, is_super_admin=True, auth_source='database'),
])
def test_only_local_authorized_super_admin_can_access_uat(user):
    assert not uat_access.local_super_admin(user)


def test_fails_closed_before_resource_discovery(monkeypatch):
    app = Flask(__name__)
    app.config['SOURCE_CONTROL_GITHUB_UAT_ENABLED'] = False
    monkeypatch.setattr(
        uat_access, 'provider_kind',
        lambda *_: SimpleNamespace(available=True),
    )
    with app.app_context():
        with pytest.raises(NotFound):
            uat_access.require_uat_access()


def test_fails_closed_for_non_admin_when_enabled(monkeypatch):
    app = Flask(__name__)
    app.config['SOURCE_CONTROL_GITHUB_UAT_ENABLED'] = True
    monkeypatch.setattr(
        uat_access, 'provider_kind',
        lambda *_: SimpleNamespace(available=True),
    )
    monkeypatch.setattr(uat_access, 'current_user', _actor(admin=False))
    with app.app_context():
        with pytest.raises(Forbidden):
            uat_access.require_uat_access()


def test_uat_routes_are_isolated_and_do_not_call_github_during_get():
    root = Path(__file__).resolve().parents[2]
    file = root / (
        'app/integrations/source_control/source_control/providers/github/'
        'application/uat_routes.py'
    )
    source = file.read_text()
    assert "url_prefix='/integrations/source-control/github/uat'" in source
    assert "require_uat_access()" in source
    assert "read_installation_inventory(" in source
    assert "enqueue_github_app_job(" in source
    assert "enqueue_source_repository_sync(" in source
    assert "@permission_required('integrations.manage')" in source
    assert "FlaskForm().validate_on_submit()" in source
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
    detail = root.joinpath(
        'app/templates/integrations/source_control/github/uat_detail.html'
    ).read_text()
    assert 'filter_by(installation_id=installation.id)' in routes
    assert 'SourceWebhookDelivery.received_at.desc()' in routes
    assert 'delivery.dispatched_job_execution_id' in detail
    assert 'delivery.processing_state' in detail
    assert 'delivery.payload_sha256' not in detail
    assert 'delivery.repository_native_id_hint' not in detail
    assert 'page_hero.context_card(' in detail
