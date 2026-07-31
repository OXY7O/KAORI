from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_configmap_and_secret_delete_use_final_confirmation_modal() -> None:
    for domain, modal_id, submit_id in (
        ('configmaps', 'configmap-delete-confirmation', 'configmap-delete-submit'),
        ('secrets', 'secret-delete-confirmation', 'secret-delete-submit'),
    ):
        page = read(f'app/templates/kubernetes_operations/{domain}/delete.html')
        actions = read(f'app/templates/kubernetes_operations/{domain}/_delete_actions.html')

        assert 'components/destructive_confirmation_modal.html' in page
        assert modal_id in page
        assert 'js/destructive_confirmation_modal.js' in page
        assert 'data-destructive-modal-open' in actions
        assert submit_id in actions
        assert 'class="hidden"' in actions


def test_destructive_confirmation_modal_has_accessible_focus_management() -> None:
    component = read('app/templates/components/destructive_confirmation_modal.html')
    script = read('app/static/js/destructive_confirmation_modal.js')

    assert 'role="dialog"' in component
    assert 'aria-modal="true"' in component
    assert 'data-destructive-modal-close' in component
    assert 'data-destructive-modal-confirm' in component
    assert 'data-destructive-target-scope' in component
    assert "event.key === 'Escape'" in script
    assert "event.key !== 'Tab'" in script
    assert 'selectedOptions[0]' in script
    assert 'opener?.focus()' in script
