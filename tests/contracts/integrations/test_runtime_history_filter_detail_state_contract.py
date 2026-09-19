from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_HISTORY = ROOT / 'app/templates/integrations/partials/_runtime_history.html'
DIALOG_CONTROLLER = ROOT / 'app/static/js/native_dialogs.js'
RECORD_ACTIONS = ROOT / 'app/templates/integrations/components/_record_actions.html'


def test_runtime_history_detail_uses_shared_native_dialog_instead_of_expandable_state():
    source = RUNTIME_HISTORY.read_text()
    actions = RECORD_ACTIONS.read_text()

    assert 'integrations/components/_runtime_observation_modal.html' in source
    assert 'runtime_observation_modal.render(' in source
    assert 'record_actions.view_more(' in source
    assert "row.detail_id ~ '-dialog'" in source
    assert 'data-kaori-dialog-open' in actions
    assert 'data-dialog-target="{{ dialog_target }}"' in actions
    assert 'data-detail-toggle' not in source
    assert 'data-kaori-runtime-observation-detail' not in source
    assert 'x-data="{ open: false }"' not in source


def test_runtime_history_filter_swap_recreates_closed_native_dialogs():
    source = RUNTIME_HISTORY.read_text()
    modal = (ROOT / 'app/templates/integrations/components/_runtime_observation_modal.html').read_text()

    assert 'hx-swap="outerHTML"' in source
    assert 'hx-trigger="change delay:100ms"' in source
    assert 'integrations/components/_record_detail_modal.html' in modal
    assert 'record_detail_modal.render(' in modal
    assert "size='standard'" in modal
    assert '<dialog' not in modal


def test_shared_native_dialog_controller_owns_open_close_behavior():
    source = DIALOG_CONTROLLER.read_text()

    assert "const openSelector = '[data-kaori-dialog-open]'" in source
    assert 'dialog.showModal()' in source
    assert 'dialog.close()' in source
    assert 'event.target === dialog' in source
