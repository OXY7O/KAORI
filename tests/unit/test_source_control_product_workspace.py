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


@pytest.mark.parametrize(
    'endpoint, args',
    [(routes.overview, ()), (routes.repositories, ()), (routes.section, ('signals',))],
)
def test_product_routes_enforce_uat_guard_before_scoped_data(monkeypatch, endpoint, args):
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
            endpoint.__wrapped__(*args)


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
    operations = (root / 'app/templates/source_control/partials/_dashboard_operations.html').read_text()
    inventory = (root / 'app/templates/source_control/repositories.html').read_text()
    reusable = (root / 'app/templates/integrations/source_control/github/_inventory_table.html').read_text()
    for text in (overview, inventory):
        assert 'components/page_hero.html' in text
        assert 'components/operational_section_card.html' in text
        assert '<style' not in text
    assert 'GitHub Account</th>' in operations
    assert 'item.account.native_account_id' in operations
    assert 'item.account.last_observed_at' in operations
    assert 'Account Not Observed' in operations
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
        'components/table_registry.html',
    ):
        assert reference in overview
    evidence_partials = (
        (template_dir / 'partials/_dashboard_inventory_snapshot.html').read_text(),
        (template_dir / 'partials/_dashboard_data_freshness.html').read_text(),
    )
    assert all('components/operational_evidence_tile.html' in partial for partial in evidence_partials)
    assert 'components/info_tip.html' not in evidence_partials[1]
    assert 'dashboard_workspace.panel(tab_key, active_dashboard_tab' in overview
    assert 'hx-trigger="revealed"' in overview
    assert "url_for('source_control.section', section=tab_key" in overview
    assert 'section_loading.section(' in overview
    assert 'eager_health_pagination' in overview
    assert "dashboard_workspace.navigation('source-control-dashboard'" in overview
    assert 'data-kaori-source-control-product' in overview
    operations = (template_dir / 'partials/_dashboard_operations.html').read_text()
    assert 'GitHub Account</th>' in operations
    assert 'item.installation.id' in operations
    assert 'scope.has_more' in overview
    assert 'scope.latest_committed_at' in overview
    assert 'No Active GitHub Installations' in operations
    assert 'source_control/partials/_dashboard_inventory_snapshot.html' in operations
    assert 'source_control/partials/_dashboard_data_freshness.html' in operations
    assert 'Installation Health Summary' in operations
    assert 'Operational Health' not in overview
    assert 'Committed Evidence' not in overview
    assert 'Evidence & Analytics Boundaries' not in overview
    assert 'table_registry.footer(' in operations
    assert 'for item in installation_rows' in operations
    assert 'MetricsConsumer' not in overview
    assert 'request.' not in overview
    assert '<script' not in overview and '<style' not in overview

    env = Environment(loader=FileSystemLoader(str(root / 'app/templates')))
    env.filters['user_datetime'] = lambda dt: dt.isoformat() if dt else 'Not Collected'
    env.parse(overview)
    for name in (
        'capacity',
        'signals',
        'reporting',
        'reporting_summary',
        'reporting_guidance',
        'inventory_snapshot',
        'data_freshness',
        'operations',
        'section',
        'repository_portfolio',
        'repository_composition',
        'repository_attention',
    ):
        env.parse((template_dir / 'partials' / f'_dashboard_{name}.html').read_text())

    committed_at = datetime(2026, 10, 26, tzinfo=UTC)
    installation = {
        'committed': True,
        'observed_count': 0,
        'coverage': 'exhaustive_installation_grants',
        'selection_scope': 'all_repositories',
        'collection_status': 'committed',
        'account': SimpleNamespace(last_observed_at=committed_at),
        'last_committed_at': committed_at,
    }
    scope = {
        'installations': (installation,),
        'installation_count': 1,
        'committed_count': 1,
        'uncollected_count': 0,
        'has_more': False,
        'latest_committed_at': committed_at,
    }

    def url(endpoint, **kwargs):
        path = '/' + endpoint.replace('.', '/')
        if 'installation_id' in kwargs:
            path += f'?installation_id={kwargs["installation_id"]}'
        return path

    coverage = SimpleNamespace(
        collected=True,
        collection_status='committed',
        observed_count=0,
        grant_count=0,
        grant_count_matches_observation=True,
        collection_coverage='exhaustive_installation_grants',
        selection_scope='all_repositories',
        committed_at=committed_at,
        lifecycle=(SimpleNamespace(count=0), SimpleNamespace(count=0)),
        visibility=(),
        references=(),
        attention_count=0,
        attention=(),
        single_repository=None,
    )
    panels = {
        name: env.get_template(f'source_control/partials/_dashboard_{name}.html')
        for name in ('capacity', 'signals', 'reporting')
    }
    for name, panel in panels.items():
        blocked = panel.render(
            scope=scope,
            selected_scope=False,
            selected_installation_id=None,
            repository_coverage=None,
            url_for=url,
        )
        assert 'data-kaori-blocked-state' in blocked, name
        assert 'Select Installation' in blocked, name
        assert 'Installation Required' in blocked, name
        assert 'Not Qualified' not in blocked, name

        selected = panel.render(
            scope=scope,
            selected_scope=True,
            selected_installation_id=11,
            repository_coverage=coverage,
            url_for=url,
        )
        assert 'data-kaori-blocked-state' not in selected, name
        assert 'Select Installation' not in selected, name
        if name == 'capacity':
            assert 'Verified Empty' in selected, name
        else:
            assert 'Not Qualified' in selected, name

    capacity_selected = panels['capacity'].render(
        scope=scope,
        selected_scope=True,
        selected_installation_id=11,
        repository_coverage=coverage,
        url_for=url,
    )
    assert 'Repository Portfolio Snapshot' in capacity_selected
    assert 'Repository Composition' in capacity_selected
    assert 'Repository Attention & Evidence Gaps' in capacity_selected
    assert 'Observed Repositories' in capacity_selected
    assert 'All Repositories' in capacity_selected
    assert 'Verified Empty' in capacity_selected
    assert 'Engineering Demand Evidence' not in capacity_selected

    signals_selected = panels['signals'].render(
        scope=scope, selected_scope=True, selected_installation_id=11, url_for=url
    )
    assert 'Alerts Summary' in signals_selected
    assert 'Source Control Alerts Not Yet Qualified' in signals_selected
    assert 'Alert Interpretation & Response' in signals_selected
    assert 'Controlled Response Flow' in signals_selected
    assert 'Recommended Actions' in signals_selected
    assert 'Recommendations Not Yet Qualified' in signals_selected
    assert 'Unavailable' in signals_selected
    assert '0 Active' not in signals_selected

    reporting_selected = panels['reporting'].render(
        scope=scope, selected_scope=True, selected_installation_id=11, url_for=url
    )
    assert '2026-10-26T00:00:00+00:00' in reporting_selected
    assert 'Reporting Summary' in reporting_selected
    assert 'Reporting Workflow' in reporting_selected
    assert 'Recent Evidence Activity' in reporting_selected
    assert 'Account Observation' in reporting_selected
    assert 'Reporting Boundary' in reporting_selected
    assert 'PR, CI, DORA' in reporting_selected
    assert 'Scope Bound' in reporting_selected
    assert 'Governed Flow' in reporting_selected
    assert 'Manual Review' in reporting_selected
    assert 'Recurring' in reporting_selected and 'Not Qualified' in reporting_selected
    assert 'Generated Reports' not in reporting_selected
    assert 'Report Templates' not in reporting_selected
    assert '0 Active' not in reporting_selected
    assert '?installation_id=11' in reporting_selected

    no_collection = {
        **scope,
        'committed_count': 0,
        'uncollected_count': 1,
        'latest_committed_at': None,
        'installations': (
            {
                **installation,
                'committed': False,
                'observed_count': None,
                'collection_status': 'not_collected',
                'last_committed_at': None,
            },
        ),
    }
    absent = panels['capacity'].render(
        scope=no_collection,
        selected_scope=True,
        selected_installation_id=11,
        repository_coverage=SimpleNamespace(collected=False),
        url_for=url,
    )
    assert 'Unknown' in absent
    assert 'Not Collected' in absent
    assert 'Unavailable' in absent


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
            assert context['eager_health_pagination'] is (
                'installation_page' in query or 'installation_per_page' in query
            )

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
    overview = (folder / 'partials/_dashboard_operations.html').read_text()
    snapshot = (folder / 'partials/_dashboard_inventory_snapshot.html').read_text()
    freshness = (folder / 'partials/_dashboard_data_freshness.html').read_text()
    k8s = (root / 'app/templates/kubernetes/dashboard/partials/_overview.html').read_text()

    assert 'peer_content_grid.layout_classes()' in k8s
    assert "section_intro.render('Operational Health'" not in overview
    assert "section_intro.render('Committed Evidence'" not in overview
    assert 'peer_grid.layout_classes()' in overview
    assert "peer_grid.column_classes('primary')" in overview
    assert "peer_grid.column_classes('secondary')" in overview
    assert 'section_card.render(' in overview
    assert 'table_registry.footer(' in overview
    assert "'installation_page'" in overview
    assert "'installation_per_page'" in overview
    assert 'authorized_scope_has_more' in overview
    assert 'item.account.native_account_id' in overview
    assert 'item.observed_count if item.observed_count is not none else' in overview
    assert 'No Active GitHub Installations' in overview
    assert 'operational_evidence_tile.html' in snapshot
    assert 'body_classes=' in snapshot and 'extra_classes=' in snapshot
    assert 'evidence_tile.snapshot(' in snapshot
    assert 'operational_evidence_tile.html' in freshness
    assert 'evidence_tile.freshness(' in freshness
    assert 'source-control-evidence-guide' not in freshness
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
    qualified_reads = []

    def read_coverage(*, authorized_installation_id):
        qualified_reads.append(authorized_installation_id)
        return SimpleNamespace(installation_id=authorized_installation_id)

    monkeypatch.setattr(routes, 'read_repository_coverage_for_current_session', read_coverage)
    captured = []

    def capture(template, **context):
        captured.append(context)
        return 'rendered'

    monkeypatch.setattr(routes, '_uncached_render', capture)
    for selected_id, committed, expected_time in (
        ('11', 1, committed_at),
        ('22', 0, None),
    ):
        initial_read_count = len(qualified_reads)
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
            assert context['repository_coverage'] is None
            assert len(qualified_reads) == initial_read_count

            # Capacity analytics are loaded only by the authorized lazy endpoint.
            with app.test_request_context(
                '/source-control/section/capacity',
                query_string={'installation_id': selected_id},
            ):
                assert routes.section.__wrapped__('capacity') == 'rendered'
                section_context = captured[-1]
                assert section_context['repository_coverage'].installation_id == int(selected_id)
                assert section_context['section_key'] == 'capacity'

    with app.test_request_context('/source-control/'):
        assert routes.overview.__wrapped__() == 'rendered'
        context = captured[-1]
        assert context['scope'] is authorized
        assert context['selected_installation_id'] is None
        assert context['installation_pagination']['total_items'] == 2
        assert context['repository_coverage'] is None
        assert qualified_reads == [11, 22]


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
    operations = (folder / 'partials/_dashboard_operations.html').read_text()
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
    assert 'selected_scope = selected_installation_id is not none' in overview
    assert "'Selected Inventory Retained'" in overview
    assert "'Selected Inventory Not Collected'" in overview
    assert "'Visible Scope Collected'" in overview
    assert "'Selected Installation' if selected_scope" in overview
    assert "'Selected Inventory Commit' if selected_scope" in overview
    assert "{'tab': 'overview', 'installation_id': selected_installation_id or ''}" in operations
    assert "selected_installation_name or 'All Authorized Installations'" in overview
    assert 'table_ui.header_cell_classes(action=true)' in operations
    assert 'table_ui.cell_classes(action=true)' in operations
    assert "item.observed_count if item.observed_count is not none else 'Unknown'" in operations
    assert "item.collection_status == 'committed'" in operations
    assert 'account.last_observed_at' in overview
    assert 'Repository observations are shown only for a single' not in inventory
    for description in (
        'Committed inventory is retained in KAORI. Live GitHub health is not verified.',
        'Account identity was observed in KAORI. Current access is not verified.',
        'PR, CI and DORA measurements need their own committed evidence source.',
        'Reports and deployment lineage require separately qualified source evidence.',
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

    with app.test_request_context('/source-control/', query_string={'tab': 'reporting', 'installation_id': '11'}):
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


def test_source_control_overview_compact_text_table_and_scope_gate_contract():
    root = Path(__file__).resolve().parents[2] / 'app/templates/source_control'
    overview = (root / 'overview.html').read_text()
    operations = (root / 'partials/_dashboard_operations.html').read_text()
    freshness = (root / 'partials/_dashboard_data_freshness.html').read_text()

    for caption in (
        'Authorized GitHub installations.',
        'Committed installation scopes.',
        'Uncollected installation scopes.',
        'Latest retained inventory date.',
        'Selected authorized installation.',
        'Inventory retained for this grant.',
        'Grant awaiting collection.',
        'Selected inventory commit date.',
    ):
        assert caption in overview
        assert len(caption) <= 36

    assert 'min-w-[1024px]' not in operations
    assert 'hidden table-fixed xl:table' in operations
    assert 'data-source-control-installation-cards' in operations
    assert 'data-source-control-installation-table' in operations
    assert 'overflow-x-auto' not in operations
    assert '<colgroup>' in operations
    assert 'title="Observed repositories per installation"' in operations
    assert 'text-right tabular-nums' in operations
    assert "item.observed_count if item.observed_count is not none else 'Unknown'" in operations
    assert 'table_registry.footer(' in operations

    for phrase in (
        'Committed inventory is retained in KAORI. Live GitHub health is not verified.',
        'Account identity was observed in KAORI. Current access is not verified.',
        'PR, CI and DORA measurements need their own committed evidence source.',
        'Reports and deployment lineage require separately qualified source evidence.',
    ):
        assert phrase in freshness

    for name in ('capacity', 'signals', 'reporting'):
        partial = (root / 'partials' / f'_dashboard_{name}.html').read_text()
        assert '{% if not selected_scope %}' in partial
        assert 'components/states/_blocked_state.html' in partial
        assert 'Installation Required' in partial
        assert 'Select Installation' in partial
        if name == 'capacity':
            assert 'source_control/partials/_dashboard_repository_portfolio.html' in partial
            assert 'source_control/partials/_dashboard_repository_composition.html' in partial
            assert 'source_control/partials/_dashboard_repository_attention.html' in partial
        elif name == 'signals':
            assert 'alert_summary.render(' in partial
            assert 'alert_response.render(' in partial
            assert 'recommendation_cards.render(' in partial
            assert 'source_available=false' in partial
        else:
            assert 'peer_content_grid.layout_classes()' in partial
            assert 'source_control/partials/_dashboard_reporting_summary.html' in partial
            assert 'source_control/partials/_dashboard_reporting_guidance.html' in partial
            assert 'section_intro.render(' not in partial
            assert 'info_tip.render(' not in partial


def test_source_control_health_register_reflows_without_horizontal_scrolling():
    """Wide screens use the shared table; narrower screens use the same scoped rows."""
    root = Path(__file__).resolve().parents[2] / 'app/templates/source_control'
    overview = (root / 'partials/_dashboard_operations.html').read_text()
    freshness = (root / 'partials/_dashboard_data_freshness.html').read_text()

    assert "table_ui.table_classes('hidden table-fixed xl:table')" in overview
    assert 'data-source-control-installation-table' in overview
    assert 'data-source-control-installation-cards' in overview
    assert 'xl:hidden' in overview
    assert 'overflow-x-auto' not in overview
    assert 'min-w-[1024px]' not in overview
    assert overview.count('{% for item in installation_rows %}') == 2
    assert overview.count('source_control.repositories') >= 3
    assert overview.count("item.observed_count if item.observed_count is not none else 'Unknown'") == 2
    assert overview.count('item.installation.native_installation_id') >= 2
    assert overview.count('item.account.native_account_id') >= 2
    assert 'Account Observed' in overview
    assert 'item.account.last_observed_at|user_datetime' in overview
    assert '<colgroup>' in overview
    assert 'w-[13%]' in overview
    assert 'text-right tabular-nums' in overview
    assert 'Last Committed' in overview
    assert 'table_registry.footer(' in overview
    assert 'No Active GitHub Installations' in overview
    assert 'Operational Health' not in overview
    assert 'Committed Evidence' not in overview
    assert 'section_intro.html' not in overview
    assert 'components/info_tip.html' not in freshness
    assert 'header_badge=' not in freshness
    assert 'source-control-evidence-guide' not in freshness


def test_source_control_repository_coverage_reuses_dashboard_and_qualified_chart_patterns():
    """The panel follows Kubernetes' two peers + lower detail hierarchy."""
    from jinja2 import Environment, FileSystemLoader

    root = Path(__file__).resolve().parents[2] / 'app/templates'
    overview = (root / 'source_control/overview.html').read_text()
    capacity = (root / 'source_control/partials/_dashboard_capacity.html').read_text()
    k8s = (root / 'kubernetes/dashboard/partials/_capacity.html').read_text()
    portfolio = (root / 'source_control/partials/_dashboard_repository_portfolio.html').read_text()
    composition = (root / 'source_control/partials/_dashboard_repository_composition.html').read_text()
    attention = (root / 'source_control/partials/_dashboard_repository_attention.html').read_text()

    assert "'capacity', 'Repository Coverage', 'folder-git-2'" in overview
    assert 'dashboard_workspace.panel(tab_key' in overview
    assert 'tabs=source_control_tabs' in overview
    assert 'peer_grid.layout_classes()' in capacity
    assert 'peer_content_grid.layout_classes()' in k8s
    assert 'components/states/_blocked_state.html' in capacity
    assert 'Repository Portfolio Snapshot' in portfolio
    assert 'components/operational_evidence_tile.html' in portfolio
    assert 'Repository Composition' in composition
    assert 'components/progress_bar.html' in composition
    assert 'data-source-control-single-repository' in composition
    assert 'data-source-control-repository-distributions' in composition
    assert 'Repository Attention & Evidence Gaps' in attention
    assert 'repository_coverage.attention' in attention
    assert 'components/operational_section_card.html' in attention
    assert 'Not Qualified' not in capacity
    assert 'Engineering Demand Evidence' not in capacity
    assert 'Forecast & Growth Risk' not in capacity
    assert 'source_control.repositories' in attention
    for template in (capacity, portfolio, composition, attention):
        assert '<script' not in template
        assert '<style' not in template
        assert 'requests.get' not in template

    env = Environment(loader=FileSystemLoader(str(root)))
    env.filters['user_datetime'] = lambda d: d.isoformat() if d else 'Not Collected'

    def url(endpoint, **kwargs):
        return '/' + endpoint.replace('.', '/') + '?installation_id=' + str(kwargs.get('installation_id', ''))

    def category(label, count, percent):
        return SimpleNamespace(label=label, count=count, percent=percent)

    common = {
        'collected': True,
        'collection_status': 'committed',
        'observed_count': 1,
        'grant_count': 1,
        'grant_count_matches_observation': True,
        'collection_coverage': 'exhaustive_installation_grants',
        'selection_scope': 'selected',
        'committed_at': datetime(2026, 10, 26, tzinfo=UTC),
        'visibility': (category('Private', 1, 100),),
        'lifecycle': (category('Active', 1, 100), category('Archived', 0, 0)),
        'references': (category('Branch Only', 1, 100),),
        'attention_count': 1,
        'attention': (SimpleNamespace(name='org/repo', reasons=('Exact SHA Missing',)),),
        'single_repository': 'org/repo',
    }
    panel = env.get_template('source_control/partials/_dashboard_capacity.html')
    all_scope = panel.render(selected_scope=False, repository_coverage=None, url_for=url)
    assert 'data-kaori-blocked-state' in all_scope
    assert 'Select Installation' in all_scope
    assert 'Repository Portfolio Snapshot' not in all_scope

    single = panel.render(
        selected_scope=True,
        selected_installation_id=11,
        repository_coverage=SimpleNamespace(**common),
        url_for=url,
    )
    assert 'data-source-control-single-repository' in single
    assert 'data-source-control-repository-distributions' not in single
    assert 'org/repo' in single
    assert 'Exact SHA Missing' in single
    assert '2026-10-26T00:00:00+00:00' in single
    assert 'Repository Attention & Evidence Gaps' in single
    assert '?installation_id=11' in single

    multi = panel.render(
        selected_scope=True,
        selected_installation_id=11,
        repository_coverage=SimpleNamespace(
            **{
                **common,
                'observed_count': 2,
                'grant_count': 2,
                'visibility': (category('Private', 1, 50), category('Public', 1, 50)),
                'lifecycle': (category('Active', 2, 100), category('Archived', 0, 0)),
                'references': (category('Exact SHA', 1, 50), category('Branch Only', 1, 50)),
                'single_repository': None,
            }
        ),
        url_for=url,
    )
    assert 'data-source-control-repository-distributions' in multi
    assert 'role="progressbar"' in multi
    assert 'Public' in multi and 'Private' in multi
    assert '50%' in multi

    missing = panel.render(
        selected_scope=True,
        selected_installation_id=11,
        repository_coverage=SimpleNamespace(**{**common, 'collected': False}),
        url_for=url,
    )
    assert 'Repository Inventory Unavailable' in missing
    assert 'Repository Composition Unavailable' in missing
    assert 'Evidence Gaps Not Yet Qualified' in missing
    assert 'data-source-control-repository-distributions' not in missing

    zero = panel.render(
        selected_scope=True,
        selected_installation_id=11,
        repository_coverage=SimpleNamespace(**{**common, 'observed_count': 0, 'grant_count': 0, 'attention_count': 0}),
        url_for=url,
    )
    assert 'No Repositories in the Retained Grant' in zero
    assert 'Zero repository grants were observed' in zero


def test_source_control_lazy_sections_match_shared_dashboard_and_keep_pagination():
    """Each tab is fetched once revealed, while the scope filter retains the active tab."""
    root = Path(__file__).resolve().parents[2] / 'app/templates'
    shell = (root / 'source_control/overview.html').read_text()
    section = (root / 'source_control/partials/_dashboard_section.html').read_text()
    operations = (root / 'source_control/partials/_dashboard_operations.html').read_text()
    k8s = (root / 'kubernetes/dashboard/partials/_content.html').read_text()
    object_storage = (root / 'storage/object_storage/dashboard/partials/_content.html').read_text()
    footer = (root / 'components/table_registry.html').read_text()
    pagination = (root / 'components/pagination.html').read_text()

    for standard in (shell, k8s, object_storage):
        assert 'hx-trigger="revealed"' in standard
        assert 'hx-target="this"' in standard
        assert 'hx-swap="outerHTML"' in standard
        assert 'section_loading.section(' in standard
    assert 'hx-sync="this:replace"' in shell
    assert "url_for('source_control.section', section=tab_key" in shell
    assert 'dashboard_workspace.panel(tab_key, active_dashboard_tab' in shell
    assert 'source-control-dashboard-active-tab' in shell
    assert 'hx-include="#source-control-dashboard-active-tab"' in shell
    assert 'hx-select="#source-control-overview"' in shell
    assert 'hx-push-url="true"' in shell
    assert 'eager_health_pagination' in shell
    assert 'source_control/partials/_dashboard_operations.html' in shell
    assert 'section_key == ' in section
    assert 'source_control/partials/_dashboard_signals.html' in section
    assert 'source_control/partials/_dashboard_reporting.html' in section
    assert 'source_control/partials/_dashboard_capacity.html' in section
    assert 'source-control-dashboard-section-overview' in operations
    assert "table_registry.footer('source_control.overview'" in operations
    assert 'path_params={}' in operations
    assert 'path_params=none' in footer
    assert 'path_params if path_params is not none' in footer
    assert 'path_params.copy() if path_params is not none' in pagination
    assert 'path_params=path_params' in footer
    assert 'source_control.section' not in footer
    assert 'section_intro.render(' not in shell
    assert 'section_intro.render(' not in section


@pytest.mark.parametrize('tab', ['overview', 'capacity', 'signals', 'reporting'])
def test_source_control_lazy_section_authorizes_scope_and_follows_selected_tab(monkeypatch, tab):
    """No installation projection is read before the independent section scope check."""
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    now = datetime(2026, 10, 26, tzinfo=UTC)
    allowed = {
        'installation': SimpleNamespace(id=11),
        'connection': SimpleNamespace(name='GitHub authorized 11'),
        'committed': True,
        'last_committed_at': now,
    }
    authorized = {
        'installations': (allowed,),
        'installation_count': 1,
        'committed_count': 1,
        'uncollected_count': 0,
        'has_more': False,
        'latest_committed_at': now,
    }
    monkeypatch.setattr(routes, 'build_source_control_overview', lambda: authorized)
    projection_ids = []

    def read_coverage(*, authorized_installation_id):
        projection_ids.append(authorized_installation_id)
        return SimpleNamespace(installation_id=authorized_installation_id)

    monkeypatch.setattr(routes, 'read_repository_coverage_for_current_session', read_coverage)
    captured = []

    def render(template, **context):
        captured.append((template, context))
        return 'rendered'

    monkeypatch.setattr(routes, '_uncached_render', render)

    with app.test_request_context(
        f'/source-control/section/{tab}',
        query_string={'installation_id': '11', 'installation_page': '1'},
        headers={'HX-Request': 'true'},
    ):
        assert routes.section.__wrapped__(tab) == 'rendered'
    template, context = captured[-1]
    assert template == 'source_control/partials/_dashboard_section.html'
    assert context['section_key'] == tab
    assert context['dashboard_active_tab'] == tab
    assert context['selected_installation_id'] == 11
    assert context['selected_scope']
    assert context['scope']['installations'] == (allowed,)
    if tab == 'capacity':
        assert context['repository_coverage'].installation_id == 11
    else:
        assert context['repository_coverage'] is None
    assert projection_ids == ([11] if tab == 'capacity' else [])

    with app.test_request_context(f'/source-control/section/{tab}', headers={'HX-Request': 'true'}):
        assert routes.section.__wrapped__(tab) == 'rendered'
        _, context = captured[-1]
        assert not context['selected_scope']
        assert context['selected_installation_id'] is None
        assert context['scope'] is authorized
    assert projection_ids == ([11] if tab == 'capacity' else [])


@pytest.mark.parametrize('value', ['12', '0', '-1', 'a', '../11', '9' * 40])
def test_source_control_lazy_section_denies_out_of_scope_or_invalid_installation(monkeypatch, value):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: {'installations': ({'installation': SimpleNamespace(id=11)},), 'has_more': False},
    )
    monkeypatch.setattr(
        routes,
        'read_repository_coverage_for_current_session',
        lambda **_kwargs: pytest.fail('Unauthorized installation analytics read'),
    )
    with app.test_request_context(
        '/source-control/section/capacity',
        query_string={'installation_id': value},
        headers={'HX-Request': 'true'},
    ):
        with pytest.raises(NotFound):
            routes.section.__wrapped__('capacity')


def test_source_control_lazy_section_rejects_unapproved_tab_before_data(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: pytest.fail('Unapproved lazy section queried committed data'),
    )
    with app.test_request_context('/source-control/section/unapproved'):
        with pytest.raises(NotFound):
            routes.section.__wrapped__('unapproved')


def test_source_control_signals_reuses_intelligence_and_never_invents_alerts():
    """Source Control uses the admitted K8s signal composition with explicit unqualified evidence."""
    from jinja2 import Environment, FileSystemLoader

    root = Path(__file__).resolve().parents[2] / 'app/templates'
    signals = (root / 'source_control/partials/_dashboard_signals.html').read_text()
    k8s_signals = (root / 'kubernetes/dashboard/partials/_signals.html').read_text()
    recommendation_macro = (root / 'components/operational_recommendation_cards.html').read_text()
    for required in (
        'peer_grid.layout_classes()',
        'alert_summary.render(',
        'alert_response.render(',
        'recommendation_cards.render(',
        'source_available=false',
        'components/states/_blocked_state.html',
    ):
        assert required in signals
    assert 'peer_content_grid.layout_classes()' in k8s_signals
    assert 'Collection Readiness' not in signals
    assert 'section_intro.render(' not in signals
    assert 'info_tip.render(' not in signals
    assert 'recommendation_count ~ ' in recommendation_macro
    assert "if source_available else 'Not Qualified'" in recommendation_macro
    assert 'Recommendations Not Yet Qualified' in recommendation_macro
    assert '0 Active' not in signals

    env = Environment(loader=FileSystemLoader(str(root)))
    env.filters['user_datetime'] = lambda d: d.isoformat() if d else 'Not Collected'
    panel = env.get_template('source_control/partials/_dashboard_signals.html')

    def url(endpoint, **_kwargs):
        return '/' + endpoint.replace('.', '/')

    blocked = panel.render(selected_scope=False, url_for=url)
    assert 'data-kaori-blocked-state' in blocked
    assert 'Select Installation' in blocked
    assert 'Alerts Summary' not in blocked

    selected = panel.render(selected_scope=True, selected_installation_id=11, url_for=url)
    assert 'Alerts Summary' in selected
    assert 'Alert Interpretation & Response' in selected
    assert 'Recommended Actions' in selected
    assert 'Source Control Alerts Not Yet Qualified' in selected
    assert 'Recommendations Not Yet Qualified' in selected
    assert '0 Active' not in selected
    assert 'No Active Recommendations' not in selected
    assert '0 Active Alert' not in selected
    assert 'Critical' in selected and 'Warning' in selected and 'Info' in selected
    assert 'Validate' in selected and 'Record' in selected
    assert 'Not Qualified' in selected
    assert '<script' not in signals and '<style' not in signals

    macro = env.get_template('components/operational_recommendation_cards.html').module.render
    default = macro(
        [],
        'Qualified recommendations',
        'test-recommendations',
        'No qualified recommendations in an admitted source.',
    )
    assert 'No Active Recommendations' in default
    assert '0 Active' in default
    unavailable = macro(
        [],
        'Unqualified source',
        'test-unqualified',
        'Not to be mistaken for an empty healthy source.',
        source_available=False,
        unavailable_description='Source mapping is not admitted.',
    )
    assert 'Recommendations Not Yet Qualified' in unavailable
    assert 'Source mapping is not admitted.' in unavailable
    assert '0 Active' not in unavailable


def test_source_control_reporting_matches_shared_peer_workflow_and_qualified_evidence():
    """Source Control reporting is inventory evidence, not synthetic generated report output."""
    from jinja2 import Environment, FileSystemLoader

    root = Path(__file__).resolve().parents[2] / 'app/templates'
    reporting = (root / 'source_control/partials/_dashboard_reporting.html').read_text()
    summary = (root / 'source_control/partials/_dashboard_reporting_summary.html').read_text()
    guidance = (root / 'source_control/partials/_dashboard_reporting_guidance.html').read_text()
    shared = (root / 'components/reporting_dashboard_workspace.html').read_text()
    k8s = (root / 'kubernetes/dashboard/partials/_reporting.html').read_text()

    assert 'peer_content_grid.layout_classes()' in k8s
    assert 'peer_content_grid.layout_classes()' in reporting
    assert "column_classes('primary', 'seven-five')" in reporting
    assert "column_classes('secondary', 'seven-five')" in reporting
    assert 'source_control/partials/_dashboard_reporting_summary.html' in reporting
    assert 'source_control/partials/_dashboard_reporting_guidance.html' in reporting
    assert 'section_intro.render(' not in reporting
    assert 'info_tip.render(' not in reporting
    assert 'reporting_workspace.evidence_summary(' in summary
    assert 'reporting_workspace.guidance(' in guidance
    assert 'evidence_only=true' in guidance
    assert 'evidence_only=false' in shared
    assert 'Generated Reports' not in summary
    assert 'Report Templates' not in summary

    env = Environment(loader=FileSystemLoader(str(root)))
    env.filters['user_datetime'] = lambda dt: dt.isoformat() if dt else 'Not Collected'
    panel = env.get_template('source_control/partials/_dashboard_reporting.html')
    def url(endpoint, **kwargs):
        return '/' + endpoint.replace('.', '/') + '?installation_id=' + str(kwargs.get('installation_id', ''))
    recorded = datetime(2026, 10, 26, tzinfo=UTC)
    selected = {
        'account': SimpleNamespace(last_observed_at=recorded),
        'committed': True,
        'observed_count': 0,
    }
    scope = {'installations': (selected,), 'latest_committed_at': recorded}
    blocked = panel.render(scope=scope, selected_scope=False, url_for=url)
    assert 'data-kaori-blocked-state' in blocked
    assert 'Select Installation' in blocked
    assert 'Reporting Summary' not in blocked

    qualified_zero = panel.render(
        scope=scope,
        selected_scope=True,
        selected_installation_id=11,
        selected_installation_name='GitHub Grant 11',
        url_for=url,
    )
    assert 'Reporting Summary' in qualified_zero
    assert 'Reporting Workflow' in qualified_zero
    assert 'Evidence Only' in qualified_zero
    assert 'Repository Evidence' in qualified_zero
    assert '0</p>' in qualified_zero
    assert 'Recent Evidence Activity' in qualified_zero
    assert 'Retained Installation Inventory' in qualified_zero
    assert 'Report Source Not Qualified' in qualified_zero
    assert 'Manual Review' in qualified_zero
    assert 'Recurring' in qualified_zero and 'Not Qualified' in qualified_zero
    assert 'Generate Report Request' not in qualified_zero
    assert 'Generated Reports' not in qualified_zero
    assert '?installation_id=11' in qualified_zero

    no_collection = panel.render(
        scope={
            **scope,
            'installations': ({**selected, 'committed': False, 'observed_count': None},),
            'latest_committed_at': None,
        },
        selected_scope=True,
        selected_installation_id=11,
        selected_installation_name='GitHub Grant 11',
        url_for=url,
    )
    assert 'No Retained Inventory Activity' in no_collection
    assert 'Inventory Not Collected' in no_collection
    assert 'Repository Evidence' in no_collection
    assert 'Unknown' in no_collection
    assert 'Evidence Pending' in no_collection
    assert 'Not Qualified' in no_collection
    assert 'Available' not in no_collection

    # Legacy operational dashboards keep their existing qualified reporting workflow.
    workflow = env.get_template('components/reporting_dashboard_workspace.html').module.guidance
    standard = workflow('Selected Cluster', 'Committed cluster evidence', 'cluster')
    assert 'One-time' in standard
    assert 'Recurring' in standard and 'Schedule' in standard
    assert 'Report Source Not Qualified' not in standard

