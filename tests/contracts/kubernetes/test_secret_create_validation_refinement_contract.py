from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_create_secret_route_uses_create_service_dry_run_keyword() -> None:
    route = read('app/kubernetes_operations/secrets/routes.py')
    create_service = read('app/kubernetes_operations/secrets/create_service.py')

    assert 'def execute_secret_operation(form: Any, files: Any, *, dry_run: bool)' in create_service
    assert 'execute_secret_operation(request.form, request.files, dry_run=True)' in route
    assert 'execute_secret_operation(request.form, request.files, dry_run=False)' in route
    assert 'execute_secret_operation(request.form, request.files, validate_only=' not in route


def test_operation_action_bar_separates_title_from_helper_copy() -> None:
    component = read('app/templates/components/form_action_bar.html')
    wrapper = read('app/templates/components/kubernetes_operation_ui.html')

    assert "title=None" in component
    assert "form_action_bar.render(description, aria_label, title)" in wrapper
    assert "title ~ ' — ' ~ description" not in wrapper


def test_secret_creation_summary_is_open_and_delete_actions_do_not_leak_on_full_page() -> None:
    create = read('app/templates/kubernetes_operations/secrets/create.html')
    delete_result = read('app/templates/kubernetes_operations/secrets/_delete_operation_result.html')

    creation_index = create.index("'Creation Summary'")
    summary_window = create[creation_index:creation_index + 240]
    assert 'open_by_default=true' in summary_window
    assert "request.headers.get('HX-Request') == 'true'" in delete_result
