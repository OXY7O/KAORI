from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from app.kubernetes_operations.secrets import routes


def _payload(*, valid: bool) -> dict[str, object]:
    return {
        'validation': SimpleNamespace(
            is_valid=valid,
            parsed_certificate=SimpleNamespace(common_name='api.example.com') if valid else None,
        )
    }


def test_tls_rotation_validation_enables_only_the_matching_form() -> None:
    app = Flask(__name__)

    with app.test_request_context('/'):
        response = routes._build_tls_rotation_preview_response('<div>validated</div>', _payload(valid=True))

    assert response.headers['HX-Trigger'] == (
        '{"kaori:operation-validated":{"formId":"tls-secret-rotate-form"}}'
    )


def test_tls_rotation_failed_validation_does_not_enable_update() -> None:
    app = Flask(__name__)

    with app.test_request_context('/'):
        response = routes._build_tls_rotation_preview_response('<div>failed</div>', _payload(valid=False))

    assert 'HX-Trigger' not in response.headers


def test_kubernetes_administration_tab_normalization() -> None:
    from app.platform_operations.kubernetes import routes as administration_routes

    assert administration_routes._active_administration_tab('secret-reveal') == 'secret-reveal'
    assert administration_routes._active_administration_tab('overview') == 'overview'
    assert administration_routes._active_administration_tab('unknown') == 'overview'
