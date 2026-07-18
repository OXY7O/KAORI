from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_inventory_exposes_instances_and_bindings_navigation():
    template = (ROOT / 'app/templates/integrations/prometheus.html').read_text()
    assert "url_for('prometheus.instances')" in template
    assert 'Instances & Bindings' in template


def test_prometheus_instances_page_renders_canonical_bindings():
    template = (ROOT / 'app/templates/prometheus/instances.html').read_text()
    routes = (ROOT / 'app/prometheus/routes.py').read_text()
    assert 'row.bindings' in template
    assert "prometheus.delete_instance_binding" in template
    assert "'bindings': bindings" in routes
