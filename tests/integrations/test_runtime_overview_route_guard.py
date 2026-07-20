from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_runtime_row_targets_instance_workspace() -> None:
    source = (ROOT / 'app/integrations/service.py').read_text(encoding='utf-8')
    assert "'detail_endpoint': 'prometheus.instance_detail'" in source
    assert "'detail_kwargs': {'instance_id': instance.id}" in source


def test_runtime_overview_defends_against_unbound_legacy_rows() -> None:
    template = (
        ROOT / 'app/templates/integrations/partials/_runtime_overview.html'
    ).read_text(encoding='utf-8')
    assert "detail_endpoint == 'prometheus.configuration'" in template
    assert "not detail_kwargs.get('cluster_id')" in template
    assert "detail_endpoint = 'prometheus.instance_detail'" in template
