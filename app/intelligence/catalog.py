from __future__ import annotations

from typing import Any

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple, unique_by

_ALLOWED_DOMAINS = {'kubernetes', 'object_storage', 'server', 'hci'}
_ALLOWED_SEVERITIES = {'critical', 'warning', 'info'}
_ALLOWED_STATUSES = {'available', 'reserved', 'imported_signal'}


def _load_catalog() -> list[dict[str, object]]:
    document = load_definition_document('intelligence/rules.yaml', expected_kind='intelligence_rules')
    raw_rules = [
        require_mapping(item, f'rules[{index}]')
        for index, item in enumerate(require_list(document.get('rules'), 'rules'))
    ]
    unique_by(raw_rules, 'rule_key', 'rules')
    rules: list[dict[str, object]] = []
    for index, raw in enumerate(raw_rules):
        path = f'rules[{index}]'
        domain = require_str(raw, 'domain', path)
        severity = require_str(raw, 'severity', path)
        status = require_str(raw, 'status', path)
        if domain not in _ALLOWED_DOMAINS:
            raise DefinitionError(f'{path}.domain is unsupported: {domain!r}.')
        if severity not in _ALLOWED_SEVERITIES:
            raise DefinitionError(f'{path}.severity is unsupported: {severity!r}.')
        if status not in _ALLOWED_STATUSES:
            raise DefinitionError(f'{path}.status is unsupported: {status!r}.')
        rule: dict[str, object] = dict(raw)
        for key in (
            'rule_key', 'title', 'source_kind', 'category', 'priority', 'logic_type', 'signal_source',
            'summary', 'condition_summary', 'recommended_action', 'impact', 'evidence_boundary',
        ):
            require_str(raw, key, path)
        if 'supported_sources' in raw:
            rule['supported_sources'] = list(string_tuple(raw.get('supported_sources'), f'{path}.supported_sources'))
        if 'visible_in' in raw:
            rule['visible_in'] = list(string_tuple(raw.get('visible_in'), f'{path}.visible_in'))
        if 'provider_keys' in raw:
            rule['provider_keys'] = list(string_tuple(raw.get('provider_keys'), f'{path}.provider_keys'))
        rules.append(rule)
    return rules


INTELLIGENCE_CATALOG: list[dict[str, object]] = _load_catalog()
