from __future__ import annotations

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple, unique_by

_ALLOWED_DOMAINS = {'kubernetes', 'object_storage', 'server', 'hci'}
_ALLOWED_SEVERITIES = {'critical', 'warning', 'info'}
_ALLOWED_STATUSES = {'available', 'reserved', 'imported_signal'}
_ALLOWED_RISK_EXCEPTION_SCOPES = {'rule_asset', 'finding_keys'}


def _normalize_risk_exception(raw_exception: object, *, path: str) -> dict[str, object]:
    if raw_exception is None:
        return {
            'enabled': False,
            'default_scope_mode': 'finding_keys',
            'allowed_scope_modes': [],
            'guidance': '',
        }
    exception_path = f'{path}.risk_exception'
    exception = require_mapping(raw_exception, exception_path)
    enabled = exception.get('enabled', False)
    if not isinstance(enabled, bool):
        raise DefinitionError(f'{exception_path}.enabled must be true or false.')
    allowed_scopes = list(
        string_tuple(exception.get('allowed_scope_modes', []), f'{exception_path}.allowed_scope_modes')
    )
    unsupported_scopes = sorted(set(allowed_scopes) - _ALLOWED_RISK_EXCEPTION_SCOPES)
    if unsupported_scopes:
        raise DefinitionError(
            f'{exception_path}.allowed_scope_modes contains unsupported values: {unsupported_scopes!r}.'
        )
    if enabled and not allowed_scopes:
        allowed_scopes = ['finding_keys', 'rule_asset']
    default_scope = str(exception.get('default_scope_mode') or 'finding_keys').strip()
    if enabled and default_scope not in allowed_scopes:
        raise DefinitionError(f'{exception_path}.default_scope_mode must be one of the allowed scope modes.')
    return {
        'enabled': enabled,
        'default_scope_mode': default_scope,
        'allowed_scope_modes': allowed_scopes,
        'guidance': str(exception.get('guidance') or '').strip(),
    }


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
            'rule_key',
            'title',
            'source_kind',
            'category',
            'priority',
            'logic_type',
            'signal_source',
            'summary',
            'condition_summary',
            'recommended_action',
            'impact',
            'evidence_boundary',
        ):
            require_str(raw, key, path)
        if 'supported_sources' in raw:
            rule['supported_sources'] = list(string_tuple(raw.get('supported_sources'), f'{path}.supported_sources'))
        if 'visible_in' in raw:
            rule['visible_in'] = list(string_tuple(raw.get('visible_in'), f'{path}.visible_in'))
        if 'provider_keys' in raw:
            rule['provider_keys'] = list(string_tuple(raw.get('provider_keys'), f'{path}.provider_keys'))
        if 'catalog_summary' in raw:
            rule['catalog_summary'] = require_str(raw, 'catalog_summary', path)
        rule['risk_exception'] = _normalize_risk_exception(raw.get('risk_exception'), path=path)
        if 'severity_bands' in raw:
            bands = require_list(raw.get('severity_bands'), f'{path}.severity_bands')
            normalized_bands: list[dict[str, object]] = []
            for band_index, item in enumerate(bands):
                band_path = f'{path}.severity_bands[{band_index}]'
                band = require_mapping(item, band_path)
                band_severity = require_str(band, 'severity', band_path)
                if band_severity not in _ALLOWED_SEVERITIES:
                    raise DefinitionError(f'{band_path}.severity is unsupported: {band_severity!r}.')
                if band.get('min_value') is None and band.get('max_value') is None:
                    raise DefinitionError(f'{band_path} requires min_value or max_value.')
                for bound in ('min_value', 'max_value'):
                    if band.get(bound) is not None and not isinstance(band.get(bound), (int, float)):
                        raise DefinitionError(f'{band_path}.{bound} must be numeric.')
                if (
                    band.get('min_value') is not None
                    and band.get('max_value') is not None
                    and float(band['min_value']) > float(band['max_value'])
                ):
                    raise DefinitionError(f'{band_path}.min_value cannot exceed max_value.')
                normalized_bands.append(dict(band))
            rule['severity_bands'] = normalized_bands
        rules.append(rule)
    return rules


def severity_for_observed_value(rule: dict[str, object], observed_value: float | int | None) -> str:
    """Resolve a rule-owned severity band for one observed numeric signal."""
    bands = rule.get('severity_bands')
    if observed_value is None or not isinstance(bands, list):
        return str(rule.get('severity') or 'info')
    value = float(observed_value)
    for raw in bands:
        if not isinstance(raw, dict):
            continue
        minimum = raw.get('min_value')
        maximum = raw.get('max_value')
        if minimum is not None and value < float(minimum):
            continue
        if maximum is not None and value > float(maximum):
            continue
        severity = str(raw.get('severity') or '').strip().lower()
        if severity in _ALLOWED_SEVERITIES:
            return severity
    return str(rule.get('severity') or 'info')


def minimum_severity_band_value(rule: dict[str, object], *, default: int) -> int:
    """Return the lowest configured numeric threshold that produces a finding."""
    bands = rule.get('severity_bands')
    if not isinstance(bands, list):
        return default
    values: list[float] = []
    for raw in bands:
        if isinstance(raw, dict) and raw.get('min_value') is not None:
            values.append(float(raw['min_value']))
    return int(min(values)) if values else default


def risk_exception_policy(rule_key: str) -> dict[str, object]:
    normalized = str(rule_key or '').strip()
    for rule in INTELLIGENCE_CATALOG:
        if str(rule.get('rule_key') or '').strip() != normalized:
            continue
        raw = rule.get('risk_exception')
        if isinstance(raw, dict):
            return dict(raw)
        break
    return {
        'enabled': False,
        'default_scope_mode': 'finding_keys',
        'allowed_scope_modes': [],
        'guidance': '',
    }


INTELLIGENCE_CATALOG: list[dict[str, object]] = _load_catalog()
