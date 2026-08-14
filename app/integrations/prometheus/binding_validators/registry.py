from __future__ import annotations

from threading import RLock

from app.integrations.prometheus.binding_validators.contracts import BindingValidator

_VALIDATORS: dict[str, BindingValidator] = {}
_LOCK = RLock()


def register_binding_validator(
    asset_type: str,
    validator: BindingValidator,
    *,
    replace: bool = False,
) -> None:
    key = str(asset_type or '').strip()
    if not key:
        raise ValueError('Prometheus binding validator requires an asset_type.')
    with _LOCK:
        if key in _VALIDATORS and not replace:
            raise ValueError(f'Prometheus binding validator for {key!r} is already registered.')
        _VALIDATORS[key] = validator


def get_binding_validator(asset_type: str) -> BindingValidator | None:
    return _VALIDATORS.get(str(asset_type or '').strip())
