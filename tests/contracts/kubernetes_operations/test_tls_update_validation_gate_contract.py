from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_single_tls_update_is_validation_gated():
    template = (ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotate.html').read_text()
    assert 'data-validation-gated' in template
    assert 'tls-secret-rotate-apply-button' in template
    assert 'data-validation-apply' in template


def test_bulk_tls_update_is_validation_gated():
    template = (ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotation.html').read_text()
    assert 'id="tls-secret-update-form"' in template
    assert 'data-validation-gated' in template
    assert template.count('data-validation-apply') >= 2
    assert 'data-validation-form="tls-secret-update-form"' in template
    assert 'js/validated_operations.js' in template


def test_bulk_preview_enables_only_valid_nonempty_target_set():
    routes = (ROOT / 'app/kubernetes/operations/secrets/tls_routes.py').read_text()
    validation = (ROOT / 'app/kubernetes/operations/secrets/tls_validation.py').read_text()
    assert 'def _build_bulk_tls_rotation_preview_response' in routes
    assert 'require_targets=True' in routes
    assert 'require_targets and not targets' in validation
    assert "form_id='tls-secret-update-form'" in routes


def test_form_associated_bulk_controls_invalidate_validation():
    script = (ROOT / 'app/static/js/validated_operations.js').read_text()
    assert 'target.form instanceof HTMLFormElement' in script
    assert 'data-validation-form' in script
    assert 'applyButtonsFor(form)' in script
