from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROM_DETAIL = ROOT / 'app/templates/integrations/observability/metrics_source/instance_detail.html'
ALERT_DETAIL = (
    ROOT / 'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_detail.html'
)
RUNTIME_PRESENTATION = ROOT / 'app/integrations/runtime/presentation.py'


def test_provider_tab_badges_count_registered_binding_rows() -> None:
    for path in (PROM_DETAIL, ALERT_DETAIL):
        source = path.read_text(encoding='utf-8')
        assert "(binding_rows|default([])|length|string) ~ ' Bindings'" in source
        assert 'scope_bindings|default([])' not in source


def test_binding_htmx_scope_updates_refresh_tab_and_hero_counts_without_reload() -> None:
    shared_tabs = (ROOT / 'app/templates/components/framed_workspace_tabs.html').read_text(encoding='utf-8')
    assert 'hx-swap-oob="innerHTML"' in shared_tabs
    assert 'macro badge_oob(prefix, key, badge)' in shared_tabs

    for detail_path, scope_path, prefix in (
        (
            PROM_DETAIL,
            ROOT / 'app/templates/integrations/observability/metrics_source/partials/_detail_scope.html',
            'metrics-source',
        ),
        (
            ALERT_DETAIL,
            (
                ROOT / 'app/templates/integrations/observability/alert_source'
                / 'providers/alertmanager/partials/_detail_scope.html'
            ),
            'alertmanager',
        ),
    ):
        detail = detail_path.read_text(encoding='utf-8')
        scope = scope_path.read_text(encoding='utf-8')
        assert f"value_id='{prefix}-hero-binding-count'" in detail
        expected_tab_update = (
            f"framed_workspace_tabs.badge_oob('{prefix}', 'scope', "
            "(binding_rows|length|string) ~ ' Bindings')"
        )
        assert expected_tab_update in scope
        assert "{% if request.headers.get('HX-Request') == 'true' %}" in scope
        assert f'id="{prefix}-hero-binding-count" hx-swap-oob="innerHTML"' in scope
        assert "{{ (bindings|length|string) ~ ' Bindings' }}" in scope

    # Create, validate, validation-poll, and delete all re-render the same
    # committed-state scope partial, so both outer badges follow each swap.
    metrics_web = (
        ROOT / 'app/integrations/observability/metrics_source/application/binding_web.py'
    ).read_text(encoding='utf-8')
    alertmanager_web = (
        ROOT / 'app/integrations/observability/alert_source/providers/alertmanager/application/routes.py'
    ).read_text(encoding='utf-8')
    assert metrics_web.count("partials/_detail_scope.html'") >= 5
    assert alertmanager_web.count("partials/_detail_scope.html'") >= 5


def test_persisted_kubernetes_runtime_exposes_nonempty_primary_summary() -> None:
    source = RUNTIME_PRESENTATION.read_text(encoding='utf-8')
    assert "'summary': _runtime_primary_summary(" in source
    assert 'def _runtime_primary_summary(' in source
    assert "subject = 'Kubernetes API' if 'kubernetes' in label_lower else 'Provider'" in source
