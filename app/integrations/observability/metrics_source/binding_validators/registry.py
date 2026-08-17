from __future__ import annotations

from threading import RLock

from app.integrations.observability.metrics_source.binding_validators.contracts import BindingValidator

_VALIDATORS: dict[tuple[str, str], BindingValidator] = {}
_LOCK = RLock()


def _validator_key(adapter_key: str, asset_type: str) -> tuple[str, str]:
    adapter = str(adapter_key or '').strip().lower()
    asset = str(asset_type or '').strip()
    if not adapter:
        raise ValueError('Metrics-source binding validator requires an adapter_key.')
    if not asset:
        raise ValueError('Metrics-source binding validator requires an asset_type.')
    return adapter, asset


def register_binding_validator(
    adapter_key: str,
    asset_type: str,
    validator: BindingValidator,
    *,
    replace: bool = False,
) -> None:
    key = _validator_key(adapter_key, asset_type)
    with _LOCK:
        if key in _VALIDATORS and not replace:
            raise ValueError(f'Metrics-source binding validator for {key!r} is already registered.')
        _VALIDATORS[key] = validator


def get_binding_validator(adapter_key: str, asset_type: str) -> BindingValidator | None:
    return _VALIDATORS.get(_validator_key(adapter_key, asset_type))
