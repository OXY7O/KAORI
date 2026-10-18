from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / 'app/integrations/capability_registry.py'
PROM = ROOT / 'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html'
ALERT = (
    ROOT
    / 'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html'
)


def test_provider_capability_registries_share_server_side_filtering_contract():
    helper = SHARED.read_text()
    assert 'build_capability_registry_view' in helper
    assert 'paginate_sequence' in helper
    assert 'PER_PAGE_OPTIONS' in helper
    for template in (PROM, ALERT):
        text = template.read_text()
        assert 'data-kaori-server-filtered-registry' in text
        assert 'components/loading_bar.html' in text
        assert 'hx-target="#{{ target_id }}"' in text
        assert 'hx-swap="outerHTML"' in text
        assert 'hx-indicator="#{{ loading_id }}"' in text
        assert 'data-kaori-auto-submit' in text
        assert 'x-model' not in text
        assert 'setTimeout' not in text

def test_all_provider_capability_registry_headers_lead_with_canonical_clear_filters() -> None:
    """Preserve the shared clear-first DOM order across provider adapters."""
    registry_paths = (
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html',
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html',
        'app/templates/integrations/registry/providers/harbor/partials/_capability_registry.html',
        'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html',
    )
    shared = (ROOT / 'app/templates/components/table_registry.html').read_text(encoding='utf-8')
    assert 'macro clear_filters_action(' in shared
    assert 'data-kaori-clear-filters' in shared

    for path in registry_paths:
        source = (ROOT / path).read_text(encoding='utf-8')
        header = source.split('<header', 1)[1].split('</header>', 1)[0]

        assert 'components/table_registry.html' in source, path
        assert header.count('registry_ui.clear_filters_action(') == 1, path
        assert header.count('table_label.metadata_label(') == 1, path
        assert (
            header.index('{% if filters.query')
            < header.index('registry_ui.clear_filters_action(')
            < header.index('{% endif %}', header.index('registry_ui.clear_filters_action('))
            < header.index('table_label.metadata_label(')
        ), path
        assert 'table_ui.action_classes()' in header, path
        assert "swap='outerHTML'" in header, path
        assert "marker=" in header, path
        assert 'hx-get=' in source, path
        assert 'hx-target=' in source, path
        assert 'hx-indicator=' in source, path
        assert 'value="{{ pagination.per_page }}"' in source or 'value="{{ pagination.per_page }}">' in source, path
