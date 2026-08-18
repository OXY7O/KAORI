import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_jinja_assignment(source: str, variable: str, value: str) -> bool:
    pattern = r'{%\s*set\s+' + re.escape(variable) + r"\s*=\s*([\"'])" + re.escape(value) + r'\1\s*%}'
    return re.search(pattern, source) is not None


def test_overview_only_builds_the_selected_deep_workspace() -> None:
    workspace = read('app/integrations/overview_workspace.py')
    overview = read('app/templates/integrations/overview.html')

    overview_builder = workspace.split('def build_integrations_overview(', 1)[1]
    assert "active_tab = tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog'" in overview_builder
    assert "if active_tab == 'catalog':" in overview_builder
    assert "if active_tab == 'coverage':" in overview_builder
    assert 'latest = _latest_runtime_observations()' in overview_builder
    assert overview_builder.index("if active_tab == 'catalog':") < overview_builder.index(
        'latest = _latest_runtime_observations()'
    )
    assert overview_builder.index("if active_tab == 'coverage':") < overview_builder.index(
        'latest = _latest_runtime_observations()'
    )

    assert 'framed_workspace_tabs.render_navigation(' in overview
    assert "{% if active_tab == 'catalog' %}" in overview
    assert "{% elif active_tab == 'runtime' %}" in overview
    assert '{% else %}' in overview
    assert 'x-show="activeTab === \'catalog\'"' not in overview
    assert "allowedTabs: ['catalog', 'runtime', 'coverage']" not in overview


def test_runtime_overview_reuses_one_latest_observation_snapshot_and_avoids_core_n_plus_one() -> None:
    service = read('app/integrations/service.py')
    workspace = read('app/integrations/overview_workspace.py')
    minio = read('app/integrations/storage/object_storage/providers/minio/presentation.py')

    overview_builder = workspace.split('def build_integrations_overview(', 1)[1]
    runtime_builder = service.split('def _runtime_overview_rows(', 1)[1].split(
        'def build_integration_runtime_detail', 1
    )[0]

    assert 'latest = _latest_runtime_observations()' in overview_builder
    assert 'latest=latest' in overview_builder
    assert 'build_extension_runtime_rows(latest)' in overview_builder
    assert '_latest_runtime_observations()' not in runtime_builder
    assert 'canonical = connection.integration_instance' in runtime_builder
    assert 'db.session.get(IntegrationInstance, connection.integration_instance_id)' not in runtime_builder
    assert 'selectinload(KubernetesConnection.integration_instance)' in overview_builder
    assert 'contains_eager(KubernetesConnection.cluster)' in overview_builder
    assert (
        'selectinload(MetricsSource.integration_instance).selectinload(IntegrationInstance.bindings)'
        in overview_builder
    )
    assert (
        'selectinload(AlertmanagerInstance.integration_instance).selectinload(IntegrationInstance.bindings)'
        in overview_builder
    )
    assert 'selectinload(MinioInstance.integration_instance).selectinload(IntegrationInstance.bindings)' in minio


def test_runtime_detail_reads_only_the_selected_target_observation() -> None:
    service = read('app/integrations/service.py')
    detail = service.split('def build_integration_runtime_detail(', 1)[1]

    assert 'observation = _latest_runtime_observation(integration_type, str(target_id))' in detail
    assert '_runtime_overview_rows(**runtime_args, latest=latest)' in detail
    assert 'module.build_runtime_overview_rows(latest, target_id)' in detail
    assert '_latest_runtime_observations()' not in detail


def test_overview_ready_counts_require_enabled_targets_and_domain_zero_targets_are_not_ready() -> None:
    extension = read('app/integrations/overview_extensions.py')
    service = read('app/integrations/service.py')
    overview = read('app/templates/integrations/overview.html')

    assert "if is_configured and is_enabled and readiness == 'ready'" in extension
    assert "if is_configured and (not is_enabled or readiness != 'ready')" in extension
    assert "'readiness_review': readiness_review" in extension
    assert "item.integration_instance.enabled and _kubernetes_readiness(item) == 'ready'" in service
    assert "item.enabled and item.readiness_status == 'ready'" in service

    coverage = service.split('def _coverage(', 1)[1].split('def _coverage_stats', 1)[0]
    assert 'elif total <= 0:' in coverage
    assert "posture_state, posture_label = 'not_configured', 'Not Configured'" in coverage
    assert "posture_state, posture_label = 'validation_required', 'Needs Review'" in coverage
    assert "posture_state, posture_label = 'ready', 'Ready'" in coverage
    assert 'integration_status(item.posture_state, item.posture_label' in overview
    assert 'No targets registered' in overview
    assert 'Available Domains' in overview
    assert "coverage_stats.available_domains ~ ' Available" in overview


def test_runtime_zero_states_and_lifecycle_use_canonical_kaori_state_ownership() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')

    assert has_jinja_assignment(runtime, 'empty_state_label', 'Setup Required')
    assert has_jinja_assignment(runtime, 'empty_state_title', 'No Integration Targets Registered')
    assert has_jinja_assignment(runtime, 'empty_state_action_label', 'Browse Providers')
    assert has_jinja_assignment(runtime, 'empty_state_label', 'No Results')
    assert has_jinja_assignment(runtime, 'empty_state_title', 'No Runtime Targets Match These Filters')
    assert 'components/states/_empty_state.html' in runtime
    assert 'Runtime Evidence Lifecycle' in runtime
    assert 'provider-neutral operational evidence' in runtime
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
