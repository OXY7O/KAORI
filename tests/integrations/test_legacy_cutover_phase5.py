from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_prometheus_consumer_resolves_canonical_instance():
    content = read('app/prometheus/consumer.py')
    assert 'resolve_instance_for_cluster(cluster.id)' in content
    assert 'PrometheusConfig.query' not in content
    assert 'from app.models import Cluster, PrometheusConfig' not in content


def test_unbound_instance_detail_is_available():
    routes = read('app/prometheus/routes.py')
    template = read('app/templates/prometheus/instance_detail.html')
    assert "@prometheus_bp.get('/instances/<int:instance_id>')" in routes
    assert 'cluster = _cluster_for_instance_or_404(instance)' not in routes.split('def instance_detail', 1)[1].split('@prometheus_bp.post', 1)[0]
    assert 'Runtime is standalone' in template
    assert "url_for('prometheus.instance_validate'" in template


def test_instances_page_always_exposes_runtime_detail():
    content = read('app/templates/prometheus/instances.html')
    assert 'Open runtime' in content
    assert '{% if row.primary_cluster_id %}' not in content
