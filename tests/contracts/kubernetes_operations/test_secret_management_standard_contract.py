from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_secret_mutations_use_one_service_owned_validation_boundary() -> None:
    routes = read('app/kubernetes_operations/secrets/routes.py')
    assert 'validate_then_apply' not in routes
    assert 'execute_secret_operation(request.form, request.files, dry_run=False)' in routes
    assert 'execute_secret_replacement(request.form, request.files, dry_run=False)' in routes


def test_secret_delete_receipt_is_stateless_and_user_bound() -> None:
    routes = read('app/kubernetes_operations/secrets/routes.py')
    receipts = read('app/kubernetes_operations/secrets/receipts.py')
    assert '_SECRET_DELETE_RECEIPT_SESSION_KEY' not in routes
    assert "'user_id': int(user_id)" in receipts
    assert "salt='kaori-secret-delete-validation-v2'" in receipts


def test_secret_overview_reads_current_committed_generation() -> None:
    service = read('app/kubernetes_operations/secrets/service.py')
    assert 'filter_current_generation(ConfigurationInventory.query, ConfigurationInventory)' in service


def test_secret_delete_ui_invalidates_receipt_on_target_or_confirmation_change() -> None:
    actions = read('app/templates/kubernetes_operations/secrets/_delete_actions.html')
    page = read('app/templates/kubernetes_operations/secrets/delete.html')
    script = read('app/static/js/secret_delete.js')
    assert 'data-secret-delete-validation-token' in actions
    assert 'data-secret-delete-final-action' in actions
    assert "filename='js/secret_delete.js'" in page
    assert "document.addEventListener('input', handleMutation)" in script
    assert "document.addEventListener('change', handleMutation)" in script
