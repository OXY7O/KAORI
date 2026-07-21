from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_runtime_row_targets_instance_workspace() -> None:
    source = (ROOT / 'app/integrations/service.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/integrations/partials/_runtime_overview.html').read_text(encoding='utf-8')
    assert "'provider': 'prometheus'" in source
    assert "'instance_id': str(instance.id)" in source
    assert "url_for('prometheus.instance_detail', instance_id=row.instance_id)" in template


def test_runtime_overview_has_no_cluster_configuration_fallback() -> None:
    template = (ROOT / 'app/templates/integrations/partials/_runtime_overview.html').read_text(encoding='utf-8')
    assert 'prometheus.configuration' not in template
    assert 'detail_endpoint' not in template
