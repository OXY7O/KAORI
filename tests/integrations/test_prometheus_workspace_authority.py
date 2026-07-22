from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_prometheus_consumer_resolves_canonical_instance():
    content = read('app/prometheus/consumer.py')
    assert 'resolve_prometheus_sources(' in content
    assert "get_integration('prometheus').execute(" in content
    assert 'PrometheusConfig.query' not in content
    assert 'from app.models import Cluster, PrometheusConfig' not in content


def test_unbound_instance_detail_is_available():
    routes = read('app/prometheus/routes.py')
    template = read('app/templates/prometheus/instance_detail.html')
    assert "@prometheus_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])" in routes
    assert 'cluster = _cluster_for_instance_or_404(instance)' not in routes.split('def instance_detail', 1)[1].split('@prometheus_bp.post', 1)[0]
    assert "('runtime', 'Runtime & History'" in template
    validation = read('app/templates/prometheus/partials/_detail_validation_content.html')
    assert "url_for('prometheus.instance_validate'" in validation


def test_provider_landing_always_exposes_instance_workspace():
    content = read('app/templates/integrations/prometheus/partials/_inventory_content.html')
    assert "url_for('prometheus.instance_detail', instance_id=row.instance_id)" in content
    assert 'primary_cluster_id' not in content
