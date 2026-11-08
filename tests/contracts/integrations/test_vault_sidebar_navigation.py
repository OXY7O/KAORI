"""HV-14: the *rendered* KAORI sidebar must expose Vault's Integration domain.

The older integrations_menu.html is not the active sidebar implementation.
This tests the actual WORKSPACES catalog + build_sidebar_navigation projection.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.common import workspace_navigation as nav
from app.common.workspace_navigation_catalog import WORKSPACES

ROOT = Path(__file__).resolve().parents[3]


def _sidebar(monkeypatch, endpoint: str, permissions: tuple[str, ...]):
    allowed = set(permissions)
    actor = SimpleNamespace(
        is_authenticated=True,
        has_permission=lambda key: key in allowed,
    )
    monkeypatch.setattr(
        nav,
        'url_for',
        lambda name, **params: (
            '/integrations/secrets-management'
            if name == 'integrations.secrets_management'
            else '/test/' + name.replace('.', '/')
        ),
    )
    sections = nav.build_sidebar_navigation(endpoint, actor)
    return next(
        (item for section in sections for item in section['items'] if item['key'] == 'integrations'),
        None,
    )


def test_active_sidebar_has_exactly_one_authorized_secrets_management_child(monkeypatch):
    item = _sidebar(monkeypatch, 'integrations.secrets_management', ('integrations.manage',))
    assert item is not None
    entries = [child for child in item['children'] if child['key'] == 'secrets_management']
    assert len(entries) == 1
    child = entries[0]
    assert child['label'] == 'Secrets Management'
    assert child['href'] == '/integrations/secrets-management'
    assert child['icon'] == 'key-round'
    assert child['active']
    assert item['active']
    assert [entry['key'] for entry in item['children']] == [
        'overview',
        'orchestration',
        'observability',
        'storage',
        'registry',
        'secrets_management',
        'source_control',
        'notifications',
    ]


@pytest.mark.parametrize(
    'endpoint',
    [
        'vault.index',
        'vault.new_instance',
        'vault.detail',
        'vault.edit_instance',
        'vault.validate',
        'vault.runtime_refresh',
    ],
)
def test_vault_provider_pages_keep_domain_sidebar_highlight(monkeypatch, endpoint):
    item = _sidebar(monkeypatch, endpoint, ('integrations.manage',))
    assert item is not None and item['active']
    selected = [child['key'] for child in item['children'] if child['active']]
    assert selected == ['secrets_management']


@pytest.mark.parametrize(
    'endpoint',
    [
        'integrations.overview',
        'integrations.registry',
        'integrations.storage',
        'notification_channels.index',
    ],
)
def test_other_integration_navigation_remains_distinct(monkeypatch, endpoint):
    item = _sidebar(monkeypatch, endpoint, ('integrations.manage',))
    assert item is not None
    assert not any(child['key'] == 'secrets_management' and child['active'] for child in item['children'])


@pytest.mark.parametrize(
    'permissions',
    [
        (),
        ('secrets_pki.view',),
        ('secrets_pki.sync',),
    ],
)
def test_no_integration_permission_cannot_see_provider_registration_menu(
    monkeypatch,
    permissions,
):
    assert _sidebar(monkeypatch, 'vault.index', permissions) is None


def test_domain_matches_registry_taxonomy_without_vendor_specific_menu():
    domain = next(workspace for workspace in WORKSPACES if workspace.key == 'integrations')
    entries = [entry for entry in domain.capabilities if entry.key == 'secrets_management']
    assert len(entries) == 1
    assert entries[0].permissions == ('integrations.manage',)
    assert entries[0].endpoint == 'integrations.secrets_management'
    routes = (ROOT / 'app/integrations/routes.py').read_text(encoding='utf-8')
    assert "@integrations_bp.get('/secrets-management')" in routes
    segment = routes.split("@integrations_bp.get('/secrets-management')", 1)[1]
    assert "@permission_required('integrations.manage')" in segment[:110]
    assert 'def secrets_management()' in segment[:220]
    taxonomy = (ROOT / 'app/definitions/catalogs/integrations/taxonomy.yaml').read_text(encoding='utf-8')
    assert 'key: secrets_management' in taxonomy
    assert 'workspace_endpoint: integrations.secrets_management' in taxonomy
    provider = (ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/__init__.py').read_text(
        encoding='utf-8'
    )
    assert "navigation_endpoint_prefixes=('vault.',)" in provider
    assert "domain_key='secrets_management'" in provider


def test_no_new_global_vault_menu_and_operational_rbac_is_independent():
    catalog = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text(
        encoding='utf-8',
    )
    assert "key='vault'" not in catalog
    assert "key='secrets_management'" not in catalog
    assert "'secrets_management',\n                'Secrets Management'" in catalog
    routes = (ROOT / 'app/secrets_pki/routes.py').read_text(encoding='utf-8')
    assert "@permission_required('secrets_pki.view')" in routes
    provider_routes = (
        ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py'
    ).read_text(encoding='utf-8')
    assert "@permission_required('integrations.manage')" in provider_routes
