from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'app/kubernetes_operations/secrets/tls_validation.py'


def load_validation_module():
    spec = importlib.util.spec_from_file_location('secret_tls_validation_under_test', MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(*, valid: bool, targets=None) -> dict[str, object]:
    return {
        'validation': SimpleNamespace(
            is_valid=valid,
            parsed_certificate=SimpleNamespace(common_name='api.example.com') if valid else None,
        ),
        'targets': targets or [],
    }


def test_single_tls_rotation_enables_only_valid_pair() -> None:
    validation = load_validation_module()

    assert (
        validation.validation_trigger(
            payload(valid=True),
            form_id='tls-secret-rotate-form',
        )
        == '{"kaori:operation-validated":{"formId":"tls-secret-rotate-form"}}'
    )
    assert (
        validation.validation_trigger(
            payload(valid=False),
            form_id='tls-secret-rotate-form',
        )
        is None
    )


def test_bulk_tls_rotation_requires_valid_pair_and_nonempty_targets() -> None:
    validation = load_validation_module()

    assert (
        validation.validation_trigger(
            payload(valid=True, targets=[1]),
            form_id='tls-secret-update-form',
            require_targets=True,
        )
        == '{"kaori:operation-validated":{"formId":"tls-secret-update-form"}}'
    )
    assert (
        validation.validation_trigger(
            payload(valid=True),
            form_id='tls-secret-update-form',
            require_targets=True,
        )
        is None
    )


def test_kubernetes_administration_tab_normalization_source_contract() -> None:
    source = (ROOT / 'app/platform_operations/kubernetes/routes.py').read_text()
    assert "if normalized in {'overview', 'secret-reveal'}" in source
