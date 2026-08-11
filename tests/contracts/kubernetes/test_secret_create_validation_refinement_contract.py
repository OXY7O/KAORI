from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_create_secret_route_uses_create_service_dry_run_keyword() -> None:
    route = read('app/kubernetes_operations/secrets/crud_routes.py')
    create_service = read('app/kubernetes_operations/secrets/create_service.py')
    assert 'def execute_secret_operation(form: Any, files: Any, *, dry_run: bool)' in create_service
    assert 'execute_secret_operation(request.form, request.files, dry_run=True)' in route
    assert 'execute_secret_operation(request.form, request.files, dry_run=False)' in route
    assert 'execute_secret_operation(request.form, request.files, validate_only=' not in route


def test_operation_action_bar_separates_title_from_helper_copy() -> None:
    component = read('app/templates/components/form_action_bar.html')
    wrapper = read('app/templates/components/kubernetes_operation_ui.html')
    assert 'title=None' in component
    assert 'form_action_bar.render(description, aria_label, title, embedded=embedded)' in wrapper
    assert 'form_action_bar.render(action_description or' in wrapper
    assert "title ~ ' — ' ~ description" not in wrapper


def test_secret_creation_uses_integrated_sensitive_data_guardrails_and_delete_actions_do_not_leak() -> None:
    create = read('app/templates/kubernetes_operations/secrets/create.html')
    delete_result = read('app/templates/kubernetes_operations/secrets/_delete_operation_result.html')
    assert 'Controlled Secret Creation' in create
    assert 'No KAORI Value Persistence' in create
    assert 'Secret values stay in request memory and are not stored by KAORI.' in create
    assert 'Payload-Free Feedback' in create
    assert 'Metadata Audit' in create
    assert 'Creation Summary' not in create
    assert 'view_more_content.html' not in create
    assert "request.headers.get('HX-Request') == 'true'" in delete_result
