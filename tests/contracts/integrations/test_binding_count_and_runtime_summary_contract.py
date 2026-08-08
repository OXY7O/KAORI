from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROM_DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
ALERT_DETAIL = ROOT / 'app/templates/alertmanager/instance_detail.html'
RUNTIME_PRESENTATION = ROOT / 'app/integrations/runtime/presentation.py'


def test_provider_tab_badges_count_registered_binding_rows() -> None:
    for path in (PROM_DETAIL, ALERT_DETAIL):
        source = path.read_text(encoding='utf-8')
        assert "(binding_rows|default([])|length|string) ~ ' Bindings'" in source
        assert 'scope_bindings|default([])' not in source


def test_persisted_kubernetes_runtime_exposes_nonempty_primary_summary() -> None:
    source = RUNTIME_PRESENTATION.read_text(encoding='utf-8')
    assert "'summary': _runtime_primary_summary(" in source
    assert 'def _runtime_primary_summary(' in source
    assert "subject = 'Kubernetes API' if 'kubernetes' in label_lower else 'Provider'" in source
