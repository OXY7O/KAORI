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

from app.common.workspace_authorization import local_super_admin as shared_local_super_admin
from app.common.workspace_navigation import _visible_capabilities
from app.common.workspace_navigation_catalog import WORKSPACES
from app.models.integration import IntegrationInstance
from app.models.source_control import SourceAccount, SourceInstallation, SourceRepositoryCollectionState
from app.source_control import presentation, routes


@pytest.fixture
def committed_product_db(monkeypatch):
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(
        bind=engine,
        tables=[
            IntegrationInstance.__table__,
            SourceAccount.__table__,
            SourceInstallation.__table__,
            SourceRepositoryCollectionState.__table__,
        ],
    )
    with Session(engine) as session:
        monkeypatch.setattr(presentation, 'db', SimpleNamespace(session=session))
        now = datetime.now(UTC)
        account = SourceAccount(
            provider_key='github',
            host_key='github.com',
            native_account_id='42',
            account_type='Organization',
            login='shared-org',
            last_observed_at=now,
        )
        session.add(account)
        session.flush()
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
                account_id=account.id if native_id != '200' else None,
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
    by_native_id = {item['installation'].native_installation_id: item for item in scope['installations']}
    assert by_native_id['100']['observed_count'] == 0
    assert by_native_id['100']['committed']
    assert by_native_id['200']['observed_count'] is None
    assert by_native_id['200']['coverage'] == 'unknown'
    assert not by_native_id['200']['committed']
    assert by_native_id['300']['observed_count'] == 3
    assert by_native_id['300']['collection_status'] == 'degraded'
    assert by_native_id['100']['account'].native_account_id == '42'
    assert by_native_id['100']['account'].account_type == 'Organization'
    assert by_native_id['300']['account'].id == by_native_id['100']['account'].id
    assert by_native_id['200']['account'] is None
    # Observed per-installation grants must never be summed into a global
    # repository count: the same repository may have overlapping grants.
    assert 'repository_total' not in scope


def test_product_overview_ignores_account_from_another_provider_host(committed_product_db):
    account = committed_product_db.query(SourceAccount).one()
    account.host_key = 'ghes.example.com'
    committed_product_db.flush()

    scope = presentation.build_source_control_overview()
    assert scope['installation_count'] == 3
    assert all(item['account'] is None for item in scope['installations'])


def test_product_overview_excludes_mismatched_integration_authority(committed_product_db):
    installation = committed_product_db.query(SourceInstallation).filter_by(native_installation_id='300').one()
    connection = committed_product_db.get(IntegrationInstance, installation.integration_instance_id)
    assert connection is not None
    connection.integration_type = 'artifact_registry'
    committed_product_db.flush()

    scope = presentation.build_source_control_overview()
    assert scope['installation_count'] == 2
    assert {item['installation'].native_installation_id for item in scope['installations']} == {'100', '200'}


@pytest.mark.parametrize('value', ['abc', '-1', '0', '2.5', '  ', '０', '2OR1', '9' * 64])
def test_repository_scope_rejects_malformed_installation_id_without_query(monkeypatch, value):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: {'installations': (), 'has_more': False},
    )
    monkeypatch.setattr(
        routes,
        'read_installation_inventory_for_current_session',
        lambda *_args, **_kwargs: pytest.fail('Unqualified inventory was queried'),
    )
    if not value.strip():
        return  # Empty scope legitimately opens the installation selector.
    with app.test_request_context('/source-control/repositories', query_string={'installation_id': value}):
        with pytest.raises(NotFound):
            routes.repositories.__wrapped__()


def test_repository_scope_rejects_other_installation_before_read(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: {
            'installations': (
                {
                    'installation': SimpleNamespace(id=11),
                    'connection': SimpleNamespace(name='Authorized installation'),
                },
            ),
            'has_more': False,
        },
    )
    monkeypatch.setattr(
        routes,
        'read_installation_inventory_for_current_session',
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

    monkeypatch.setattr(routes, '_require_product_uat_access', deny)
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
    assert uat_access.local_super_admin is shared_local_super_admin
    user = SimpleNamespace(
        is_authenticated=True,
        is_super_admin=False,
        auth_source='database',
        is_active=True,
        has_permission=lambda _: True,
    )
    assert _visible_capabilities(workspace, user) == ()
    monkeypatch.setattr(user, 'is_super_admin', True)
    assert len(_visible_capabilities(workspace, user)) == 2
    monkeypatch.setattr(user, 'auth_source', 'sso')
    assert _visible_capabilities(workspace, user) == ()
    monkeypatch.setattr(user, 'auth_source', 'database')
    # The product navigation remains available for UAT actors even if the
    # first provider has not yet completed availability/readiness.
    monkeypatch.setattr(uat_access, 'provider_kind', lambda *_: SimpleNamespace(available=False))
    assert len(_visible_capabilities(workspace, user)) == 2
    monkeypatch.setattr(user, 'has_permission', lambda _: False)
    assert _visible_capabilities(workspace, user) == ()


def test_product_templates_use_existing_source_control_inventory_contract():
    root = Path(__file__).resolve().parents[2]
    overview = (root / 'app/templates/source_control/overview.html').read_text()
    inventory = (root / 'app/templates/source_control/repositories.html').read_text()
    reusable = (root / 'app/templates/integrations/source_control/github/_inventory_table.html').read_text()
    for text in (overview, inventory):
        assert 'components/page_hero.html' in text
        assert 'components/operational_section_card.html' in text
        assert '<style' not in text
    assert 'GitHub Account</th>' in overview
    assert 'item.account.native_account_id' in overview
    assert 'item.account.last_observed_at' in overview
    assert 'Account Not Observed' in overview
    assert 'inventory.total is not none' in inventory
    assert 'integrations/source_control/github/_inventory_table.html' in inventory
    assert 'inventory_href_endpoint' in reusable
    assert 'inventory_htmx_endpoint' in reusable
    assert 'inventory.total is none' in reusable
    assert 'inventory.total == 0' in reusable
    assert '[5, 10, 25, 50]' in reusable
    assert 'exact_default_branch_sha' in reusable


def test_product_overview_dashboard_tabs_use_shared_contract_without_live_provider_calls(monkeypatch):
    """Only reviewed dashboard perspective keys enter the shared controller."""
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(routes, 'build_source_control_overview', lambda: {'installations': ()})
    captured = []

    def capture(template, **context):
        captured.append((template, context))
        return 'rendered'

    monkeypatch.setattr(routes, '_uncached_render', capture)
    for value, expected in (
        ('overview', 'overview'),
        ('capacity', 'capacity'),
        ('signals', 'signals'),
        ('reporting', 'reporting'),
        ('unknown', 'overview'),
        ("'; alert(1); //", 'overview'),
    ):
        with app.test_request_context('/source-control/', query_string={'tab': value}):
            assert routes.overview.__wrapped__() == 'rendered'
            template, context = captured[-1]
            assert template == 'source_control/overview.html'
            assert context['dashboard_active_tab'] == expected
            assert context['scope'] == {'installations': ()}


def test_product_dashboard_reuses_operational_framework_and_keeps_scoped_inventory():
    from jinja2 import Environment, FileSystemLoader

    root = Path(__file__).resolve().parents[2]
    template_dir = root / 'app/templates/source_control'
    overview = (template_dir / 'overview.html').read_text()
    for reference in (
        'components/operational_dashboard_workspace.html',
        'components/operational_signal_overview.html',
        'components/operational_metric_card.html',
        'components/operational_section_card.html',
        'components/peer_content_grid.html',
        'components/section_intro.html',
        'components/table_registry.html',
    ):
        assert reference in overview
    evidence_partials = (
        (template_dir / 'partials/_dashboard_inventory_snapshot.html').read_text(),
        (template_dir / 'partials/_dashboard_data_freshness.html').read_text(),
    )
    assert all('components/operational_evidence_tile.html' in partial for partial in evidence_partials)
    assert 'components/info_tip.html' in evidence_partials[1]
    for tab in ('overview', 'capacity', 'signals', 'reporting'):
        assert f"dashboard_workspace.panel('{tab}', active_dashboard_tab" in overview
    assert "dashboard_workspace.navigation('source-control-dashboard'" in overview
    assert 'data-kaori-source-control-product' in overview
    assert 'GitHub Account</th>' in overview
    assert 'item.installation.id' in overview
    assert 'scope.has_more' in overview
    assert 'scope.latest_committed_at' in overview
    assert 'No Active GitHub Installations' in overview
    assert 'source_control/partials/_dashboard_inventory_snapshot.html' in overview
    assert 'source_control/partials/_dashboard_data_freshness.html' in overview
    assert 'Installation Health Summary' in overview
    assert 'Operational Health' in overview
    assert 'Committed Evidence' in overview
    assert 'Evidence & Analytics Boundaries' not in overview
    assert 'table_registry.footer(' in overview
    assert 'for item in installation_rows' in overview
    assert 'MetricsConsumer' not in overview
    assert 'request.' not in overview
    assert '<script' not in overview and '<style' not in overview

    env = Environment(loader=FileSystemLoader(str(root / 'app/templates')))
    env.filters['user_datetime'] = lambda dt: dt.isoformat() if dt else 'Not Collected'
    env.parse(overview)
    for name in ('capacity', 'signals', 'reporting', 'inventory_snapshot', 'data_freshness'):
        env.parse((template_dir / 'partials' / f'_dashboard_{name}.html').read_text())

    scope = {
        'installation_count': 1,
        'committed_count': 1,
        'uncollected_count': 0,
        'has_more': False,
        'latest_committed_at': None,
    }

    def url(endpoint):
        return '/' + endpoint.replace('.', '/')

    capacity = env.get_template('source_control/partials/_dashboard_capacity.html')
    observed = capacity.render(scope=scope, url_for=url)
    assert '1 authorized installation scope' in observed
    assert 'Engineering Demand' in observed
    assert 'Not Qualified' in observed
    assert 'No committed history' in observed

    signals = env.get_template('source_control/partials/_dashboard_signals.html')
    collected = signals.render(scope=scope, url_for=url)
    assert 'No Visible Collection Gap' in collected
    assert 'Unavailable' in collected
    not_collected = signals.render(scope={**scope, 'uncollected_count': 1}, url_for=url)
    assert 'Review Collection' in not_collected
    assert '1 visible installation(s) without committed inventory' in not_collected
    bounded = signals.render(scope={**scope, 'has_more': True}, url_for=url)
    assert 'first 50 authorized active installations' in bounded

    reporting = env.get_template('source_control/partials/_dashboard_reporting.html')
    not_reported = reporting.render(scope=scope, url_for=url)
    assert 'Not Collected' in not_reported
    assert 'Engineering Reports' in not_reported
    assert 'Not Qualified' in not_reported
    assert '/source_control/repositories' in not_reported


def test_product_overview_installation_health_paginates_before_render(monkeypatch):
    """Overview rows follow canonical 5/10/25/50 without altering scoped evidence."""
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    scoped = tuple({'installation': SimpleNamespace(id=index)} for index in range(1, 13))
    scope = {
        'installations': scoped,
        'installation_count': len(scoped),
        'committed_count': 0,
        'uncollected_count': 12,
        'has_more': False,
        'latest_committed_at': None,
    }
    monkeypatch.setattr(routes, 'build_source_control_overview', lambda: scope)
    captured = []

    def capture(template, **context):
        captured.append((template, context))
        return 'rendered'

    monkeypatch.setattr(routes, '_uncached_render', capture)
    for query, expected_ids, expected_page, expected_per_page in (
        ({}, [1, 2, 3, 4, 5], 1, 5),
        ({'tab': 'overview', 'installation_page': '2'}, [6, 7, 8, 9, 10], 2, 5),
        ({'tab': 'overview', 'installation_page': '3'}, [11, 12], 3, 5),
        ({'installation_page': '999'}, [11, 12], 3, 5),
        ({'installation_per_page': '10'}, list(range(1, 11)), 1, 10),
        ({'installation_per_page': '99'}, [1, 2, 3, 4, 5], 1, 5),
        ({'installation_page': '-4'}, [1, 2, 3, 4, 5], 1, 5),
        ({'installation_page': 'bad'}, [1, 2, 3, 4, 5], 1, 5),
    ):
        with app.test_request_context('/source-control/', query_string=query):
            assert routes.overview.__wrapped__() == 'rendered'
            template, context = captured[-1]
            assert template == 'source_control/overview.html'
            assert context['scope'] is scope
            assert context['installation_pagination']['page'] == expected_page
            assert context['installation_pagination']['per_page'] == expected_per_page
            assert [row['installation'].id for row in context['installation_rows']] == expected_ids

    with app.test_request_context('/source-control/'):
        monkeypatch.setattr(
            routes, 'build_source_control_overview', lambda: {**scope, 'installations': (), 'installation_count': 0}
        )
        routes.overview.__wrapped__()
        assert captured[-1][1]['installation_pagination']['start_item'] == 0
        assert captured[-1][1]['installation_pagination']['end_item'] == 0


def test_product_operations_overview_matches_shared_health_and_peer_evidence_contract():
    from jinja2 import Environment, FileSystemLoader

    root = Path(__file__).resolve().parents[2]
    folder = root / 'app/templates/source_control'
    overview = (folder / 'overview.html').read_text()
    snapshot = (folder / 'partials/_dashboard_inventory_snapshot.html').read_text()
    freshness = (folder / 'partials/_dashboard_data_freshness.html').read_text()
    k8s = (root / 'app/templates/kubernetes/dashboard/partials/_overview.html').read_text()

    assert 'peer_content_grid.layout_classes()' in k8s
    assert "section_intro.render('Operational Health'" in overview
    assert "section_intro.render('Committed Evidence'" in overview
    assert 'peer_grid.layout_classes()' in overview
    assert "peer_grid.column_classes('primary')" in overview
    assert "peer_grid.column_classes('secondary')" in overview
    assert 'section_card.render(' in overview
    assert 'table_registry.footer(' in overview
    assert "'installation_page'" in overview
    assert "'installation_per_page'" in overview
    assert 'scope.has_more' in overview
    assert 'item.account.native_account_id' in overview
    assert 'item.observed_count if item.observed_count is not none else' in overview
    assert 'No Active GitHub Installations' in overview
    assert 'operational_evidence_tile.html' in snapshot
    assert 'body_classes=' in snapshot and 'extra_classes=' in snapshot
    assert 'evidence_tile.snapshot(' in snapshot
    assert 'operational_evidence_tile.html' in freshness
    assert 'evidence_tile.freshness(' in freshness
    assert 'source-control-evidence-guide' in freshness
    assert 'Not Qualified' in freshness
    assert 'Evidence & Analytics Boundaries' not in overview
    assert '<style' not in overview and '<script' not in overview

    env = Environment(loader=FileSystemLoader(str(root / 'app/templates')))
    env.filters['user_datetime'] = lambda value: value.isoformat() if value else 'Not Collected'
    for text in (overview, snapshot, freshness):
        env.parse(text)

    def url_for(endpoint):
        return '/' + endpoint.replace('.', '/')

    observed = {
        'account': SimpleNamespace(last_observed_at=datetime(2026, 10, 26, tzinfo=UTC)),
        'committed': True,
        'observed_count': 0,
    }
    single = {
        'installations': (observed,),
        'installation_count': 1,
        'committed_count': 1,
        'uncollected_count': 0,
        'has_more': False,
        'latest_committed_at': datetime(2026, 10, 26, tzinfo=UTC),
    }
    inventory = env.get_template('source_control/partials/_dashboard_inventory_snapshot.html')
    qualified_zero = inventory.render(scope=single, url_for=url_for)
    assert 'Repository Observations' in qualified_zero
    assert '0</p>' in qualified_zero
    assert 'Per Installation</p>' not in qualified_zero
    multi = inventory.render(
        scope={**single, 'installations': (observed, observed), 'installation_count': 2},
        url_for=url_for,
    )
    assert 'Per Installation' in multi
    missing = inventory.render(
        scope={
            **single,
            'installations': ({**observed, 'committed': False, 'observed_count': None},),
            'committed_count': 0,
            'uncollected_count': 1,
        },
        url_for=url_for,
    )
    assert 'Unknown' in missing

    fresh = env.get_template('source_control/partials/_dashboard_data_freshness.html')
    observed_fresh = fresh.render(scope=single)
    assert '2026-10-26T00:00:00+00:00' in observed_fresh
    assert 'Engineering Flow' in observed_fresh and 'Not Qualified' in observed_fresh
    unobserved = fresh.render(scope={**single, 'latest_committed_at': None, 'installations': ()})
    assert 'Not Collected' in unobserved
    assert 'Not Observed' in unobserved
    assert 'Unavailable' in unobserved


def test_product_overview_installation_scope_filter_restricts_authorized_committed_projection(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    committed_at = datetime(2026, 10, 26, tzinfo=UTC)
    installations = (
        {
            'installation': SimpleNamespace(id=11),
            'connection': SimpleNamespace(name='GitHub Allowed 11'),
            'committed': True,
            'collection_status': 'committed',
            'observed_count': 0,
            'last_committed_at': committed_at,
        },
        {
            'installation': SimpleNamespace(id=22),
            'connection': SimpleNamespace(name='GitHub Allowed 22'),
            'committed': False,
            'collection_status': 'not_collected',
            'observed_count': None,
            'last_committed_at': None,
        },
    )
    authorized = {
        'installations': installations,
        'installation_count': 2,
        'committed_count': 1,
        'uncollected_count': 1,
        'has_more': True,
        'latest_committed_at': committed_at,
    }
    monkeypatch.setattr(routes, 'build_source_control_overview', lambda: authorized)
    captured = []

    def capture(template, **context):
        captured.append(context)
        return 'rendered'

    monkeypatch.setattr(routes, '_uncached_render', capture)
    for selected_id, committed, expected_time in (
        ('11', 1, committed_at),
        ('22', 0, None),
    ):
        with app.test_request_context(
            '/source-control/', query_string={'installation_id': selected_id, 'tab': 'capacity'}
        ):
            assert routes.overview.__wrapped__() == 'rendered'
            context = captured[-1]
            scope = context['scope']
            assert context['dashboard_active_tab'] == 'capacity'
            assert context['selected_installation_id'] == int(selected_id)
            assert context['selected_installation_name'] == f'GitHub Allowed {selected_id}'
            assert context['authorized_installations'] is installations
            assert context['authorized_scope_has_more']
            assert scope['installation_count'] == 1
            assert scope['committed_count'] == committed
            assert scope['uncollected_count'] == 1 - committed
            assert scope['latest_committed_at'] == expected_time
            assert not scope['has_more']
            assert scope['installations'] == (installations[0 if committed else 1],)
            assert context['installation_pagination']['total_items'] == 1
            assert context['installation_rows'] == [installations[0 if committed else 1]]

    with app.test_request_context('/source-control/'):
        assert routes.overview.__wrapped__() == 'rendered'
        context = captured[-1]
        assert context['scope'] is authorized
        assert context['selected_installation_id'] is None
        assert context['installation_pagination']['total_items'] == 2


@pytest.mark.parametrize(
    'value',
    ['not-an-id', '-1', '0', '23', '999', '12x', '../22', '9' * 40],
)
def test_product_overview_rejects_unregistered_installation_scope(monkeypatch, value):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: {
            'installations': ({'installation': SimpleNamespace(id=22)},),
            'installation_count': 1,
            'has_more': False,
        },
    )
    monkeypatch.setattr(
        routes,
        '_uncached_render',
        lambda *_args, **_kwargs: pytest.fail('Unauthorized installation scope rendered'),
    )
    with app.test_request_context('/source-control/', query_string={'installation_id': value}):
        with pytest.raises(NotFound):
            routes.overview.__wrapped__()


def test_product_overview_selector_table_and_two_line_evidence_contract():
    root = Path(__file__).resolve().parents[2]
    folder = root / 'app/templates/source_control'
    overview = (folder / 'overview.html').read_text()
    inventory = (folder / 'partials/_dashboard_inventory_snapshot.html').read_text()
    freshness = (folder / 'partials/_dashboard_data_freshness.html').read_text()
    assert 'source-control-installation-filter' in overview
    assert 'All Authorized Installations' in overview
    assert 'for option in authorized_installations' in overview
    assert 'hx-trigger="change"' in overview
    assert 'hx-disabled-elt="this"' in overview
    assert 'hx-include="#source-control-dashboard-active-tab"' in overview
    assert 'hx-select="#source-control-overview"' in overview
    assert 'hx-push-url="true"' in overview
    assert 'hx-sync="closest section:replace"' in overview
    assert 'data-source-control-scope-filter' in overview
    assert '<button type="submit"' not in overview
    assert 'hx-include="closest form"' not in overview
    assert "input_id='source-control-dashboard-active-tab'" in overview
    assert "selected_scope = selected_installation_id is not none" in overview
    assert "'Selected Inventory Retained'" in overview
    assert "'Selected Inventory Not Collected'" in overview
    assert "'Visible Scope Collected'" in overview
    assert "'Selected Installation' if selected_scope" in overview
    assert "'Selected Inventory Commit' if selected_scope" in overview
    assert "{'tab': 'overview', 'installation_id': selected_installation_id or ''}" in overview
    assert "selected_installation_name or 'All Authorized Installations'" in overview
    assert 'table_ui.header_cell_classes(action=true)' in overview
    assert 'table_ui.cell_classes(action=true)' in overview
    assert "item.observed_count if item.observed_count is not none else 'Unknown'" in overview
    assert "item.collection_status == 'committed'" in overview
    assert 'account.last_observed_at' in overview
    assert 'Repository observations are shown only for a single' not in inventory
    for description in (
        'Retained inventory; not live GitHub health.',
        'Account observed; current access unverified.',
        'PR, CI and DORA evidence not yet qualified.',
        'Reports and deployment lineage not qualified.',
    ):
        assert description in freshness
    assert 'operational_evidence_tile.html' in freshness
    assert 'operational_evidence_tile.html' in inventory

    k8s = (root / 'app/templates/kubernetes/dashboard/partials/_signal_overview.html').read_text()
    for htmx_contract in (
        'hx-trigger="change"',
        'hx-disabled-elt="this"',
        'hx-push-url="true"',
        'hx-include=',
    ):
        assert htmx_contract in k8s
        assert htmx_contract in overview


def test_product_overview_one_grant_all_vs_selected_are_explicitly_scoped(monkeypatch):
    """One grant can yield equal counts; selected context must remain distinct."""
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    commit_time = datetime(2026, 10, 26, tzinfo=UTC)
    installation = {
        'installation': SimpleNamespace(id=11),
        'connection': SimpleNamespace(name='GitHub OXY7O UAT'),
        'committed': True,
        'collection_status': 'committed',
        'last_committed_at': commit_time,
        'observed_count': 1,
    }
    scope = {
        'installations': (installation,),
        'installation_count': 1,
        'committed_count': 1,
        'uncollected_count': 0,
        'has_more': False,
        'latest_committed_at': commit_time,
    }
    monkeypatch.setattr(routes, 'build_source_control_overview', lambda: scope)
    contexts = []

    def render(_template, **context):
        contexts.append(context)
        return 'rendered'

    monkeypatch.setattr(routes, '_uncached_render', render)
    with app.test_request_context('/source-control/', query_string={'tab': 'reporting'}):
        assert routes.overview.__wrapped__() == 'rendered'
    all_context = contexts[-1]
    assert all_context['scope'] is scope
    assert all_context['selected_installation_id'] is None
    assert all_context['selected_installation_name'] is None
    assert all_context['dashboard_active_tab'] == 'reporting'

    with app.test_request_context(
        '/source-control/', query_string={'tab': 'reporting', 'installation_id': '11'}
    ):
        assert routes.overview.__wrapped__() == 'rendered'
    selected = contexts[-1]
    assert selected['selected_installation_id'] == 11
    assert selected['selected_installation_name'] == 'GitHub OXY7O UAT'
    assert selected['dashboard_active_tab'] == 'reporting'
    assert selected['scope'] is not scope
    assert selected['scope']['installations'] == scope['installations']
    assert selected['scope']['committed_count'] == scope['committed_count']
    assert selected['scope']['installation_count'] == scope['installation_count']
    assert selected['installation_rows'] == all_context['installation_rows']
