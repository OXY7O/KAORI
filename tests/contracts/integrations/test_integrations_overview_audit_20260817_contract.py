from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_overview_only_builds_the_selected_deep_workspace() -> None:
    workspace = read('app/integrations/overview_workspace.py')
    overview = read('app/templates/integrations/overview.html')
    builder = workspace.split('def build_integrations_overview(', 1)[1]
    assert "active_tab = tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog'" in builder
    assert "if active_tab == 'catalog':" in builder
    assert "if active_tab == 'coverage':" in builder
    assert builder.index("if active_tab == 'coverage':") < builder.index('fleet = runtime_fleet()')
    assert 'overview_portfolio_counts()' in builder
    assert 'runtime_page(selected, page=page, per_page=per_page)' in builder
    assert 'framed_workspace_tabs.render_navigation(' in overview
    assert "{% if active_tab == 'catalog' %}" in overview
    assert "{% elif active_tab == 'runtime' %}" in overview
    assert 'x-show="activeTab' not in overview


def test_runtime_overview_reuses_scoped_latest_observations_and_hydrates_only_a_page() -> None:
    workspace = read('app/integrations/overview_workspace.py')
    query = read('app/integrations/overview_runtime_sql.py')
    assert 'specs, pagination = runtime_page(selected, page=page, per_page=per_page)' in workspace
    assert "'runtime_rows': _visible_runtime_rows(specs)" in workspace
    assert 'observation_ids = {' in workspace
    assert 'IntegrationRuntimeObservation.id.in_(observation_ids)' in workspace
    assert 'select(model).where(model.id.in_(ids)).options(*options)' in workspace
    assert 'runtime_filter(' in workspace
    assert '.offset(window.offset).limit(window.per_page)' in query
    assert 'lookup.observed_at.desc()' in query
    assert 'db.session.execute(' in query


def test_runtime_detail_reads_only_the_selected_target_observation() -> None:
    service = read('app/integrations/service.py')
    detail = service.split('def build_integration_runtime_detail(', 1)[1]

    assert 'observation = _latest_runtime_observation(integration_type, str(target_id))' in detail
    assert '_runtime_overview_rows(**runtime_args, latest=latest)' in detail
    assert 'module.build_runtime_overview_rows(latest, target_id)' in detail
    assert '_latest_runtime_observations()' not in detail


def test_overview_ready_counts_require_active_canonical_targets() -> None:
    extension = read('app/integrations/overview_extensions.py')
    sql = read('app/integrations/overview_sql.py')
    service = read('app/integrations/service.py')
    overview = read('app/templates/integrations/overview.html')
    assert 'def canonical_operational(' in extension
    assert "getattr(canonical, 'lifecycle_status', 'active') == 'active'" in extension
    assert "if is_configured and is_enabled and readiness == 'ready'" in extension
    assert "identity.lifecycle_status == 'active'" in sql
    assert "ready = and_(configured, active, state == 'ready')" in sql
    assert 'posture_state, posture_label = portfolio_posture(summary)' in service
    assert 'No targets registered' in overview
    assert 'Available Domains' in overview


def test_runtime_zero_states_and_lifecycle_use_canonical_kaori_state_ownership() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')

    assert 'empty_state_label = "Setup Required"' in runtime
    assert 'empty_state_title = "No Integration Targets Registered"' in runtime
    assert 'empty_state_action_label = "Browse Providers"' in runtime
    assert 'empty_state_label = "No Results"' in runtime
    assert 'empty_state_title = "No Runtime Targets Match These Filters"' in runtime
    assert 'components/states/_empty_state.html' in runtime
    assert 'Runtime Evidence Lifecycle' in runtime
    assert 'provider-neutral evidence' in runtime
    assert 'platform_operations.data_lifecycle.index' in runtime
    assert "domain='runtime_observation'" in runtime


def test_hero_actions_describe_persisted_overview_navigation_not_live_refresh() -> None:
    hero = read('app/templates/integrations/partials/_hero.html')
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')
    overview = read('app/templates/integrations/overview.html')

    assert 'Browse Providers' in hero
    assert 'Review Runtime' in hero
    assert 'Refresh Status' not in hero
    assert 'Reload Evidence' in runtime
    assert 'page=runtime_pagination.page' in runtime
    assert 'Map available provider workspaces' in overview
    assert 'hx-select="#integration-workspace"' in hero
    assert "url_for('integrations.overview', tab='runtime')" in hero
    assert "hx_swap='outerHTML show:none'" in overview
