from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / 'app/integrations/capability_registry.py'
PROM = ROOT / 'app/templates/metrics/partials/_capability_registry.html'
ALERT = ROOT / 'app/templates/alertmanager/partials/_capability_registry.html'


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
