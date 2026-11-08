"""Identity Provider test feedback/transport regression for KAORI UAT (#2908)."""

import ast
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_unsaved_test_connection_uses_canonical_feedback_without_inline_alert() -> None:
    routes = source('app/access/identity_providers/routes.py')
    functions = {
        node.name: ast.get_source_segment(routes, node)
        for node in ast.parse(routes).body
        if isinstance(node, ast.FunctionDef)
    }
    test_route = functions['test_configuration']
    assert test_route is not None
    assert 'identity_provider_feedback(' in test_route
    assert "'identity_provider_connection_tested'" in test_route
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in test_route
    assert any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == 'render_template'
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == 'access/identity_providers/form.html'
        for call in ast.walk(ast.parse(test_route))
    )
    assert 'test_result' not in test_route
    assert 'validate_identity_provider(candidate)' in test_route

    form = source('app/templates/access/identity_providers/form.html')
    Environment().parse(form)
    assert 'test_result' not in form
    assert 'operational_callout' not in form
    layout = source('app/templates/layouts/app.html')
    assert 'id="operational-toast-stack"' in layout
    assert 'components/operational_toast.html' in layout


def test_ldap_form_disallows_plain_even_when_dev_override_exists() -> None:
    forms = source('app/access/identity_providers/forms.py')
    assert "choices=[('ldaps', 'LDAPS'), ('starttls', 'StartTLS')]" in forms
    assert "if field.data not in {'ldaps', 'starttls'}:" in forms
    assert 'Plain (development only)' not in forms

    ldap = source('app/templates/access/identity_providers/partials/_ldap_configuration.html')
    Environment().parse(ldap)
    assert 'plaintext is not available in this form' in ldap

    # The existing lower-level adapter retains its historical development
    # compatibility flag. The administrative form never opts into plaintext.
    client = source('app/access/authentication/identity_provider/adapters/ldap/client.py')
    assert "if mode == 'plain' and not allow_plaintext:" in client


def test_provider_test_events_are_audit_owned_and_deck_on_failure_only() -> None:
    helper = source('app/access/identity_providers/notifications.py')
    assert 'delivery_policy: OperationalDeliveryPolicy | str' in helper
    assert 'delivery_policy=delivery_policy' in helper
    feedback = source('app/platform_operations/notifications/feedback.py')
    assert 'DECK_ON_FAILURE' in feedback
    assert "return status in {'warning', 'error'}" in feedback


def test_flask_debug_profiles_load_ignored_local_dotenv_without_container_recreate() -> None:
    import json

    launch = json.loads(source('.vscode/launch.json'))
    profiles = {item['name']: item for item in launch['configurations']}
    for name in ('KAORI: Flask Debug', 'KAORI: Flask Auto Reload'):
        profile = profiles[name]
        assert profile['envFile'] == '${workspaceFolder}/.env'
        assert profile['request'] == 'launch'
        assert profile['module'] == 'flask'
    gitignore = source('.gitignore')
    assert '\n.env\n' in gitignore
    assert '\n/secrets/\n' in gitignore
