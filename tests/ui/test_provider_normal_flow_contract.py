from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROM_DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
PROM_ROUTES = ROOT / 'app/prometheus/routes.py'
DEPENDENCIES = ROOT / 'app/common/dependencies.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_prometheus_hero_uses_mandatory_capability_context() -> None:
    detail = read(PROM_DETAIL)
    assert 'stats.capabilities' not in detail
    assert 'capability_summary.observed|default(0)' in detail


def test_legacy_edit_is_redirect_only() -> None:
    routes = read(PROM_ROUTES)
    section = routes[routes.index("@prometheus_bp.get('/instances/<int:instance_id>/edit')"):routes.index("@prometheus_bp.get('/instances')")]
    assert "methods=['GET', 'POST']" not in section
    assert "#configuration" in section
    assert 'save_prometheus_instance' not in section


def test_normal_templates_and_dependency_actions_do_not_force_cluster_compatibility_pages() -> None:
    sources = []
    for base in (ROOT / 'app/templates/prometheus', ROOT / 'app/templates/alertmanager', ROOT / 'app/templates/integrations'):
        sources.extend(path.read_text(encoding='utf-8') for path in base.rglob('*.html'))
    joined = '\n'.join(sources)
    assert "url_for('prometheus.configuration'" not in joined
    assert "url_for('alertmanager.cluster_alertmanager_config'" not in joined

    dependencies = read(DEPENDENCIES)
    assert "prometheus.configuration" not in dependencies
    assert "alertmanager.cluster_alertmanager_config" not in dependencies
    assert "url_for('prometheus.new_instance', cluster_id=cluster.id)" in dependencies
    assert "url_for('alertmanager.new_instance', cluster_id=cluster.id)" in dependencies


def test_legacy_prometheus_registry_and_cluster_configuration_are_redirect_boundaries() -> None:
    routes = read(PROM_ROUTES)
    registry = routes[
        routes.index("@prometheus_bp.get('/instances')"):
        routes.index("@prometheus_bp.route('/instances/<int:instance_id>'")
    ]
    assert "redirect(url_for('integrations.prometheus'))" in registry
    assert 'list_instances()' not in registry

    cluster_start = "@prometheus_bp.route(\n    '/cluster/<string:cluster_id>',"
    cluster_end = "@prometheus_bp.route(\n    '/cluster/<string:cluster_id>/test'"
    cluster = routes[routes.index(cluster_start):routes.index(cluster_end)]
    assert "url_for('prometheus.instance_detail'" in cluster
    assert "url_for('prometheus.new_instance'" in cluster
    assert 'PrometheusConfigForm' not in cluster
    assert "'prometheus/config.html'" not in cluster
