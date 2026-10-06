from __future__ import annotations

from dataclasses import dataclass

from app.definitions.integration_registry import integration_provider_matrix_document
from app.definitions.validation import require_list, require_mapping, require_str


@dataclass(frozen=True, slots=True)
class IntegrationProviderKind:
    integration_type: str
    domain_key: str
    key: str
    label: str
    adapter_key: str
    lifecycle: str
    protocol: str

    @property
    def available(self) -> bool:
        return self.lifecycle == 'available'


def _load() -> tuple[IntegrationProviderKind, ...]:
    document = integration_provider_matrix_document()
    rows: list[IntegrationProviderKind] = []
    for type_index, raw_type in enumerate(require_list(document.get('integration_types'), 'integration_types')):
        type_item = require_mapping(raw_type, f'integration_types[{type_index}]')
        integration_type = require_str(type_item, 'key', f'integration_types[{type_index}]')
        domain_key = require_str(type_item, 'domain_key', f'integration_types[{type_index}]')
        for provider_index, raw_provider in enumerate(
            require_list(type_item.get('providers'), f'integration_types[{type_index}].providers')
        ):
            provider = require_mapping(
                raw_provider,
                f'integration_types[{type_index}].providers[{provider_index}]',
            )
            path = f'integration_types[{type_index}].providers[{provider_index}]'
            rows.append(
                IntegrationProviderKind(
                    integration_type=integration_type,
                    domain_key=domain_key,
                    key=require_str(provider, 'key', path),
                    label=require_str(provider, 'label', path),
                    adapter_key=require_str(provider, 'adapter_key', path),
                    lifecycle=require_str(provider, 'lifecycle', path),
                    protocol=require_str(provider, 'protocol', path),
                )
            )
    return tuple(rows)


_PROVIDER_KINDS = _load()
_PROVIDER_INDEX = {(item.integration_type, item.key): item for item in _PROVIDER_KINDS}


def provider_kind(integration_type: str, provider_key: str) -> IntegrationProviderKind:
    identity = (str(integration_type or '').strip().lower(), str(provider_key or '').strip().lower())
    try:
        return _PROVIDER_INDEX[identity]
    except KeyError as exc:
        raise ValueError(f'Unsupported provider {provider_key!r} for integration type {integration_type!r}.') from exc


def provider_kinds(integration_type: str, *, include_planned: bool = True) -> tuple[IntegrationProviderKind, ...]:
    normalized = str(integration_type or '').strip().lower()
    rows = [item for item in _PROVIDER_KINDS if item.integration_type == normalized]
    if not include_planned:
        rows = [item for item in rows if item.available]
    return tuple(sorted(rows, key=lambda item: item.label.casefold()))


def provider_options(integration_type: str, *, include_planned: bool = False) -> list[dict[str, str]]:
    return [
        {
            'value': item.key,
            'label': item.label,
            'adapter_key': item.adapter_key,
            'lifecycle': item.lifecycle,
        }
        for item in provider_kinds(integration_type, include_planned=include_planned)
    ]
