"""Canonical Integrations Test Connection registration parity (#2921)."""

import ast
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_identity_provider_create_requires_server_side_signed_proof() -> None:
    routes = read('app/access/identity_providers/routes.py')
    functions = {
        node.name: ast.get_source_segment(routes, node)
        for node in ast.parse(routes).body
        if isinstance(node, ast.FunctionDef)
    }
    create = functions['create']
    test = functions['test_configuration']
    edit = functions['edit']
    assert create is not None and test is not None and edit is not None
    assert 'verify_registration_proof(' in create
    assert 'if not verified:' in create
    assert 'identity_provider_registration_blocked' in create
    assert create.index('verify_registration_proof(') < create.index('create_identity_provider(')
    assert 'issue_registration_proof(' in test
    assert "status, title = 'success', 'Connection Test Passed'" in test
    assert 'provider is None' in test
    assert 'registration_proof=registration_proof' in test
    assert 'verify_registration_proof(' not in edit  # Allow disable/recovery of a broken provider.


def test_new_registration_ui_starts_locked_and_invalidates_changed_fields() -> None:
    template = read('app/templates/access/identity_providers/form.html')
    Environment().parse(template)
    assert 'name="connection_test_proof"' in template
    assert 'data-registration-proof' in template
    assert 'data-registration-save' in template
    assert 'data-connection-test-state' in template
    assert 'aria-live="polite"' in template
    assert 'disabled:cursor-not-allowed' in template

    js = read('app/static/js/identity_provider_form.js')
    assert "form.addEventListener('input', invalidateRegistrationTest, true)" in js
    assert "form.addEventListener('change', invalidateRegistrationTest, true)" in js
    assert "registrationProof.value = ''" in js
    assert 'registrationSave.disabled = !verified' in js
    assert "registrationSave.setAttribute('aria-disabled', String(!verified))" in js


def test_proof_reuses_signed_10_minute_integrations_registration_pattern() -> None:
    proof = read('app/access/identity_providers/registration_proof.py')
    reference = read('app/integrations/registry/providers/harbor/application/registration.py')
    assert 'URLSafeTimedSerializer' in proof
    assert 'hmac.compare_digest' in proof
    assert 'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600' in proof
    assert 'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600' in reference
    assert "'fingerprint': _form_fingerprint(form)" in proof
    assert 'connection_test_proof' not in proof
