from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_HISTORY = ROOT / 'app/templates/integrations/partials/_runtime_history.html'
DETAIL_ROWS_JS = ROOT / 'app/static/js/detail_rows.js'


def test_runtime_history_detail_rows_use_htmx_safe_shared_toggle_state():
    source = RUNTIME_HISTORY.read_text()

    assert 'data-detail-toggle' in source
    assert 'data-detail-group="{{ runtime_history_id }}"' in source
    assert 'data-detail-static="true"' in source
    assert 'data-open="false"' in source
    assert 'class="hidden" data-kaori-runtime-observation-detail' in source

    # Per-row Alpine state caused detail visibility to drift after HTMX filter swaps.
    assert 'x-data="{ open: false }"' not in source
    assert 'x-show="open"' not in source
    assert '@click="open = !open"' not in source


def test_runtime_history_filter_swap_returns_closed_detail_rows_by_default():
    source = RUNTIME_HISTORY.read_text()

    assert 'hx-swap="outerHTML"' in source
    assert 'hx-trigger="change delay:100ms"' in source
    assert 'data-detail-state="closed"' in source
    assert 'aria-expanded="false"' in source


def test_shared_detail_row_controller_supports_static_server_rendered_details():
    source = DETAIL_ROWS_JS.read_text()

    assert "if (target.dataset.detailStatic === 'true')" in source
    assert "target.removeAttribute('aria-busy')" in source
    assert "if (!detailUrl)" in source
