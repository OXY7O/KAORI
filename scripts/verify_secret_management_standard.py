#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

routes = read('app/kubernetes_operations/secrets/routes.py')
service = read('app/kubernetes_operations/secrets/service.py')
receipts = read('app/kubernetes_operations/secrets/receipts.py')
delete_template = read('app/templates/kubernetes_operations/secrets/_delete_actions.html')
delete_page = read('app/templates/kubernetes_operations/secrets/delete.html')

assert 'validate_then_apply' not in routes
assert '_SECRET_DELETE_RECEIPT_SESSION_KEY' not in routes
assert 'issue_delete_receipt' in routes and 'verify_delete_receipt' in routes
assert "'user_id': int(user_id)" in receipts
assert 'filter_current_generation' in service
assert 'data-secret-delete-validation-token' in delete_template
assert 'data-secret-delete-final-action' in delete_template
assert "filename='js/secret_delete.js'" in delete_page
print('KAORI Secret Management Standard audit passed')
