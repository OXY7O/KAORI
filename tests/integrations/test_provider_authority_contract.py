from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_instance_detail_and_canonical_binding_ui_exist() -> None:
    routes = (ROOT / 'app/prometheus/routes.py').read_text()
    template = (ROOT / 'app/templates/prometheus/partials/_detail_scope.html').read_text()
    assert "@prometheus_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])" in routes
    assert "@prometheus_bp.get('/instances')" not in routes
    assert 'IntegrationBinding' in routes
    assert 'prometheus.add_instance_binding' in template


def test_active_consumers_do_not_read_retired_provider_configuration() -> None:
    forbidden = (
        'cluster.prometheus_config',
        'cluster.kubeconfig',
        'PrometheusConfig.query',
        'AlertmanagerConfig.query',
        'get_legacy_config_by_cluster_id',
    )
    paths = [
        ROOT / 'app/analytics', ROOT / 'app/inventory', ROOT / 'app/governance',
        ROOT / 'app/kubernetes_operations', ROOT / 'app/integrations',
        ROOT / 'app/prometheus', ROOT / 'app/alertmanager', ROOT / 'app/cluster',
    ]
    violations = []
    for base in paths:
        for path in base.rglob('*.py'):
            if path.name == 'models.py':
                continue
            text = path.read_text()
            for token in forbidden:
                if token in text:
                    violations.append(f'{path.relative_to(ROOT)}: {token}')
    assert not violations, '\n'.join(violations)
