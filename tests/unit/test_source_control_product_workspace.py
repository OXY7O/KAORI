"""Scoped Source Control product-domain regression contracts (#3375)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden, NotFound

from app.common.workspace_navigation import _visible_capabilities
from app.common.workspace_navigation_catalog import WORKSPACES
from app.models.integration import IntegrationInstance
from app.models.source_control import SourceInstallation, SourceRepositoryCollectionState
from app.source_control import presentation, routes


@pytest.fixture
def committed_product_db(monkeypatch):
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(
        bind=engine,
        tables=[
            IntegrationInstance.__table__,
            SourceInstallation.__table__,
            SourceRepositoryCollectionState.__table__,
        ],
    )
    with Session(engine) as session:
        monkeypatch.setattr(presentation, 'db', SimpleNamespace(session=session))
        now = datetime.now(UTC)
        for native_id, status, observed_count, generation in [
            ('100', 'committed', 0, 1),
            ('200', 'not_collected', None, 0),
            ('300', 'degraded', 3, 2),
        ]:
            connection = IntegrationInstance(
                name=f'GitHub installation {native_id}',
                integration_type='source_control',
                provider_key='github',
                adapter_key='github_rest_v3',
                lifecycle_status='active',
                readiness_status='validation_required',
            )
            session.add(connection)
            session.flush()
            installation = SourceInstallation(
                integration_instance_id=connection.id,
                provider_key='github',
                host_key='github.com',
                native_app_id='1',
                native_installation_id=native_id,
                repository_scope='selected',
            )
            session.add(installation)
            session.flush()
            session.add(
                SourceRepositoryCollectionState(
                    installation_id=installation.id,
                    next_generation=generation,
                    committed_generation=generation,
                    status=status,
                    repository_scope='selected',
                    coverage='exhaustive_installation_grants' if generation else 'unknown',
                    observed_count=observed_count,
                    last_committed_at=now if generation else None,
                )
            )
        session.commit()
        yield session
    engine.dispose()


def test_product_overview_preserves_verified_zero_unknown_and_degraded_history(committed_product_db):
    scope = presentation.build_source_control_overview()
    assert scope['installation_count'] == 3
    assert scope['committed_count'] == 2
    assert scope['uncollected_count'] == 1
    assert not scope['has_more']
    assert scope['latest_committed_at'] is not None
    by_native_id = {
        item['installation'].native_installation_id: item
        for item in scope['installations']
    }
    assert by_native_id['100']['observed_count'] == 0
    assert by_native_id['100']['committed']
    assert by_native_id['200']['observed_count'] is None
    assert by_native_id['200']['coverage'] == 'unknown'
    assert not by_native_id['200']['committed']
    assert by_native_id['300']['observed_count'] == 3
    assert by_native_id['300']['collection_status'] == 'degraded'
    # Observed per-installation grants must never be summed into a global
    # repository count: the same repository may have overlapping grants.
    assert 'repository_total' not in scope


@pytest.mark.parametrize('value', ['abc', '-1', '0', '2.5', '  ', '０', '2OR1', '9' * 64])
def test_repository_scope_rejects_malformed_installation_id_without_query(monkeypatch, value):
    app = Flask(__name__)
    monkeypatch.setattr(routes, 'require_uat_access', lambda: None)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: {'installations': (), 'has_more': False},
    )
    monkeypatch.setattr(
        routes,
        'read_installation_inventory',
        lambda *_args, **_kwargs: pytest.fail('Unqualified inventory was queried'),
    )
    if not value.strip():
        return  # Empty scope legitimately opens the installation selector.
    with app.test_request_context('/source-control/repositories', query_string={'installation_id': value}):
        with pytest.raises(NotFound):
            routes.repositories.__wrapped__()


def test_repository_scope_rejects_other_installation_before_read(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, 'require_uat_access', lambda: None)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: {
            'installations': ({
                'installation': SimpleNamespace(id=11),
                'connection': SimpleNamespace(name='Authorized installation'),
            },),
            'has_more': False,
        },
    )
    monkeypatch.setattr(
        routes,
        'read_installation_inventory',
        lambda *_args, **_kwargs: pytest.fail('Cross-scope inventory was queried'),
    )
    with app.test_request_context('/source-control/repositories?installation_id=12'):
        with pytest.raises(NotFound):
            routes.repositories.__wrapped__()


@pytest.mark.parametrize('endpoint', [routes.overview, routes.repositories])
def test_product_routes_enforce_uat_guard_before_scoped_data(monkeypatch, endpoint):
    app = Flask(__name__)

    def deny():
        raise Forbidden()

    monkeypatch.setattr(routes, 'require_uat_access', deny)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: pytest.fail('Read happened before resource UAT guard'),
    )
    with app.test_request_context('/source-control/'):
        with pytest.raises(Forbidden):
            endpoint.__wrapped__()


def test_product_navigation_reuses_source_control_taxonomy_and_uat_visibility(monkeypatch):
    from app.integrations.source_control import uat_access

    workspaces = [workspace for workspace in WORKSPACES if workspace.key == 'source_control']
    assert len(workspaces) == 1
    workspace = workspaces[0]
    assert workspace.section == 'Infrastructure'
    assert [entry.key for entry in workspace.capabilities] == ['overview', 'repositories']
    user = SimpleNamespace(is_authenticated=True, has_permission=lambda _: True)
    monkeypatch.setattr(uat_access, 'uat_enabled', lambda: True)
    monkeypatch.setattr(uat_access, 'local_super_admin', lambda user: False)
    assert _visible_capabilities(workspace, user) == ()
    monkeypatch.setattr(uat_access, 'local_super_admin', lambda user: True)
    assert len(_visible_capabilities(workspace, user)) == 2
    monkeypatch.setattr(uat_access, 'uat_enabled', lambda: False)
    assert _visible_capabilities(workspace, user) == ()


def test_product_templates_use_existing_source_control_inventory_contract():
    root = Path(__file__).resolve().parents[2]
    overview = (root / 'app/templates/source_control/overview.html').read_text()
    inventory = (root / 'app/templates/source_control/repositories.html').read_text()
    reusable = (
        root / 'app/templates/integrations/source_control/github/_inventory_table.html'
    ).read_text()
    for text in (overview, inventory):
        assert 'components/page_hero.html' in text
        assert 'components/operational_section_card.html' in text
        assert '<style' not in text
    assert 'inventory.total is not none' in inventory
    assert 'integrations/source_control/github/_inventory_table.html' in inventory
    assert 'inventory_href_endpoint' in reusable
    assert 'inventory_htmx_endpoint' in reusable
    assert 'inventory.total is none' in reusable
    assert 'inventory.total == 0' in reusable
    assert '[5, 10, 25, 50]' in reusable
    assert 'exact_default_branch_sha' in reusable
