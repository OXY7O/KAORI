from __future__ import annotations

import importlib.util
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_NAME = 'app.kubernetes.governance.tls_certificates'


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_certificate_module():
    module_names = (
        'app',
        'app.kubernetes.governance',
        PACKAGE_NAME,
        f'{PACKAGE_NAME}.constants',
        f'{PACKAGE_NAME}.certificate',
    )
    missing = object()
    previous_modules = {name: sys.modules.get(name, missing) for name in module_names}

    try:
        for name in ('app', 'app.kubernetes.governance', PACKAGE_NAME):
            if name not in sys.modules:
                package = types.ModuleType(name)
                package.__path__ = []  # type: ignore[attr-defined]
                sys.modules[name] = package

        _load_module(
            f'{PACKAGE_NAME}.constants',
            ROOT / 'app/kubernetes/governance/tls_certificates/constants.py',
        )
        return _load_module(
            f'{PACKAGE_NAME}.certificate',
            ROOT / 'app/kubernetes/governance/tls_certificates/certificate.py',
        )
    finally:
        for name in reversed(module_names):
            previous = previous_modules[name]
            if previous is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


certificate = _load_certificate_module()
TLSValidityPolicy = certificate.TLSValidityPolicy
classify_certificate_validity = certificate.classify_certificate_validity


def test_valid_certificate_with_less_than_one_day_remaining_is_not_expired() -> None:
    now = datetime(2026, 7, 31, 0, 0, tzinfo=UTC)
    days, status, risk = classify_certificate_validity(
        now + timedelta(hours=12),
        now=now,
        policy=TLSValidityPolicy(renewal_window_days=30, critical_window_days=7),
    )

    assert days == 1
    assert status == 'critical'
    assert risk == 'critical'


def test_certificate_expiry_uses_exact_timestamp() -> None:
    now = datetime(2026, 7, 31, 0, 0, tzinfo=UTC)
    days, status, risk = classify_certificate_validity(
        now,
        now=now,
        policy=TLSValidityPolicy(renewal_window_days=30, critical_window_days=7),
    )

    assert days == 0
    assert status == 'expired'
    assert risk == 'critical'


def test_validity_policy_clamps_critical_window_to_renewal_window() -> None:
    policy = TLSValidityPolicy(renewal_window_days=10, critical_window_days=20)

    assert policy.renewal_window_days == 10
    assert policy.critical_window_days == 10
