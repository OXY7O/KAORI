from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_operations_overview_is_permission_scoped_navigation() -> None:
    routes = read('app/kubernetes/operations/routes.py')
    menu = read('app/templates/components/navigation/kubernetes_operations_menu.html')
    page = read('app/templates/kubernetes/operations/overview.html')
    assert '@any_permission_required(' in routes
    assert "endpoint='overview'" in routes
    assert "render_template('kubernetes/operations/overview.html')" in routes
    assert "url_for('kubernetes_operations.overview')" in menu
    assert "url_for('kubernetes_operations.configmap_management')" in page
    assert "url_for('kubernetes_operations.secret_management')" in page
    assert 'data-kubernetes-operation-capabilities' in page
    assert 'current_user.has_permission(' in page
    assert 'components/workspace_link_card.html' in page


def test_both_delete_pages_use_shared_governed_confirmation() -> None:
    component = read('app/templates/components/destructive_confirmation_modal.html')
    script = read('app/static/js/destructive_confirmation_modal.js')
    for resource in ('configmaps', 'secrets'):
        page = read(f'app/templates/kubernetes/operations/{resource}/delete.html')
        assert "presentation='kubernetes'" in page
        assert 'components/destructive_confirmation_modal.html' in page
    assert "presentation == 'kubernetes'" in component
    assert 'data-destructive-target-name' in component
    assert 'data-destructive-target-scope' in component
    assert 'data-destructive-detail' in component
    assert 'data-destructive-modal-confirm' in component
    assert 'selectedOptions[0]' in script
    assert 'opener?.focus()' in script
