from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_inventory_uses_canonical_registry_and_coverage_tabs():
    template = (ROOT / 'app/templates/integrations/prometheus.html').read_text()
    assert "integration_tabs.render('prometheus'" in template
    assert "integrations/prometheus/partials/_instance_inventory.html" in template
    assert "url_for('prometheus.instances')" not in template


def test_prometheus_instance_workspace_renders_canonical_bindings():
    template = (ROOT / 'app/templates/prometheus/partials/_detail_scope.html').read_text()
    presentation = (ROOT / 'app/prometheus/presentation.py').read_text()
    assert 'bindings' in template
    assert "prometheus.delete_instance_binding" in template
    assert "'bindings': bindings" in presentation
