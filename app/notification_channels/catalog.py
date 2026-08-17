from __future__ import annotations

from app.definitions.loader import load_definition_document
from app.definitions.validation import require_mapping, require_str

_DELIVERY_CONTRACT = load_definition_document(
    'notifications/outbound_delivery.yaml',
    expected_kind='notification_delivery_contract',
)
_DOMAIN_DEFINITIONS = require_mapping(_DELIVERY_CONTRACT.get('domains'), 'domains')
_EVENT_DEFINITIONS = require_mapping(_DELIVERY_CONTRACT.get('events'), 'events')


def domain_keys() -> tuple[str, ...]:
    return tuple(str(key) for key in _DOMAIN_DEFINITIONS)


def event_type_keys() -> tuple[str, ...]:
    return tuple(str(key) for key in _EVENT_DEFINITIONS)


def domain_label(key: str) -> str:
    normalized = str(key or '').strip()
    raw = _DOMAIN_DEFINITIONS.get(normalized)
    if raw is None:
        return normalized.replace('_', ' ').title() or 'Unknown Domain'
    definition = require_mapping(raw, f'domains.{normalized}')
    return require_str(definition, 'label', f'domains.{normalized}')


def event_type_label(key: str) -> str:
    normalized = str(key or '').strip()
    raw = _EVENT_DEFINITIONS.get(normalized)
    if raw is None:
        return normalized.replace('_', ' ').replace('.', ' ').title() or 'Unknown Event'
    definition = require_mapping(raw, f'events.{normalized}')
    return require_str(definition, 'label', f'events.{normalized}')


def event_severity_scoped(key: str) -> bool:
    normalized = str(key or '').strip()
    raw = _EVENT_DEFINITIONS.get(normalized)
    if raw is None:
        return False
    definition = require_mapping(raw, f'events.{normalized}')
    return bool(definition.get('severity_scoped', False))


def domain_options() -> list[dict[str, str]]:
    return [{'value': key, 'label': domain_label(key)} for key in domain_keys()]


def event_type_options() -> list[dict[str, str]]:
    return [{'value': key, 'label': event_type_label(key)} for key in event_type_keys()]
