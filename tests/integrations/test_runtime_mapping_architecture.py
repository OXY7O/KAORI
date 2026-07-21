from pathlib import Path


def test_prometheus_runtime_is_standalone_and_bound():
    provider = Path('app/models/prometheus.py').read_text()
    integration = Path('app/models/integration.py').read_text()
    assert "__tablename__ = 'prometheus_instances'" in provider
    assert "__tablename__ = 'prometheus_bindings'" not in provider
    assert "__tablename__ = 'integration_bindings'" in integration
    assert 'asset_type' in integration
    assert 'asset_key' in integration


def test_selected_cluster_fallback_uses_registration_order():
    source = Path('app/analytics/common/clusters.py').read_text()
    assert 'item.created_at' in source
    assert 'clusters[0]' not in source


def test_runtime_panels_do_not_build_cluster_routes_in_template():
    source = Path('app/templates/prometheus/partials/_runtime_panel.html').read_text()
    assert 'cluster.id' not in source
    assert 'runtime_state.refresh_url' in source
    assert "url_for('prometheus.refresh_runtime'" not in source
    assert "url_for('prometheus.runtime_refresh_status', instance_id=instance.id" in source


def test_inventory_and_analytics_templates_do_not_use_strftime():
    roots = (Path('app/templates/inventory'), Path('app/templates/analytics'))
    offenders = []
    for root in roots:
        for path in root.rglob('*.html'):
            text = path.read_text()
            if 'strftime' in text or 'astimezone' in text or '.isoformat(' in text:
                offenders.append(str(path))
    assert offenders == []
