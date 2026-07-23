from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.models.knowledge import KnowledgeRunbookRevision
from app.resolver.registry import ResolverRegistry

_SEMVER_RE = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$')
_ALLOWED_SCHEMA_TYPES = {'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'}


class RunbookValidationError(ValueError):
    """Raised when a draft is not safe or complete enough to publish."""


@dataclass(frozen=True, slots=True)
class PublicationValidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    resolver_action: str
    required_capabilities: tuple[str, ...]
    compatibility_profiles: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            'valid': self.valid,
            'errors': list(self.errors),
            'warnings': list(self.warnings),
            'resolver_action': self.resolver_action,
            'required_capabilities': list(self.required_capabilities),
            'compatibility_profiles': list(self.compatibility_profiles),
        }


def parse_semantic_version(version: str) -> tuple[int, int, int]:
    match = _SEMVER_RE.fullmatch(str(version or '').strip())
    if match is None:
        raise RunbookValidationError('Runbook version must use semantic versioning: MAJOR.MINOR.PATCH.')
    return tuple(int(match.group(index)) for index in (1, 2, 3))


def validate_version_transition(*, previous_version: str | None, candidate_version: str, change_level: str) -> None:
    candidate = parse_semantic_version(candidate_version)
    if previous_version is None:
        return
    previous = parse_semantic_version(previous_version)
    expected = {
        'patch': (previous[0], previous[1], previous[2] + 1),
        'minor': (previous[0], previous[1] + 1, 0),
        'major': (previous[0] + 1, 0, 0),
    }.get(change_level)
    if expected is None:
        raise RunbookValidationError('Change level must be patch, minor, or major.')
    if candidate != expected:
        raise RunbookValidationError(
            f'{change_level.title()} change from {previous_version} must publish as '
            f'{expected[0]}.{expected[1]}.{expected[2]}.'
        )


def validate_parameter_schema(schema: Mapping[str, Any]) -> None:
    if not isinstance(schema, Mapping):
        raise RunbookValidationError('Parameter schema must be a JSON object.')
    schema_type = schema.get('type', 'object')
    if schema_type != 'object':
        raise RunbookValidationError('Runbook parameter schema root type must be object.')
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    if not isinstance(properties, Mapping):
        raise RunbookValidationError('Parameter schema properties must be an object.')
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise RunbookValidationError('Parameter schema required must be a list of property names.')
    unknown_required = sorted(set(required) - set(properties))
    if unknown_required:
        raise RunbookValidationError(f'Required schema properties are not defined: {", ".join(unknown_required)}.')
    for name, definition in properties.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(definition, Mapping):
            raise RunbookValidationError('Every parameter property requires a name and schema object.')
        item_type = definition.get('type')
        if item_type not in _ALLOWED_SCHEMA_TYPES:
            raise RunbookValidationError(f'Unsupported JSON schema type for {name}: {item_type}.')
    if schema.get('additionalProperties', False) is not False:
        raise RunbookValidationError('Runbook parameter schema must set additionalProperties to false.')


def validate_parameter_values(schema: Mapping[str, Any], values: Mapping[str, Any]) -> None:
    validate_parameter_schema(schema)
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    missing = sorted(name for name in required if name not in values)
    unknown = sorted(set(values) - set(properties))
    if missing:
        raise RunbookValidationError(f'Required parameters are missing: {", ".join(missing)}.')
    if unknown:
        raise RunbookValidationError(f'Unknown parameters are not allowed: {", ".join(unknown)}.')
    python_types = {
        'string': str,
        'integer': int,
        'number': (int, float),
        'boolean': bool,
        'array': list,
        'object': dict,
        'null': type(None),
    }
    for name, value in values.items():
        expected = properties[name].get('type')
        expected_type = python_types.get(expected)
        if expected_type is not None and not isinstance(value, expected_type):
            raise RunbookValidationError(f'Parameter {name} must be {expected}.')


def validate_publication(
    revision: KnowledgeRunbookRevision,
    *,
    resolver_registry: ResolverRegistry,
    available_capabilities: Sequence[str] = (),
    compatibility_profile: str | None = None,
    previous_published_version: str | None = None,
) -> PublicationValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        validate_parameter_schema(revision.parameter_schema_json or {})
    except RunbookValidationError as exc:
        errors.append(str(exc))
    try:
        validate_version_transition(
            previous_version=previous_published_version,
            candidate_version=revision.version,
            change_level=revision.change_level,
        )
    except RunbookValidationError as exc:
        errors.append(str(exc))

    required_evidence = tuple(sorted(set(revision.required_evidence_json or ())))
    if not required_evidence:
        errors.append('Published runbooks must declare required evidence.')
    required_capabilities = tuple(sorted(set(revision.required_capabilities_json or ())))
    missing_capabilities = sorted(set(required_capabilities) - set(available_capabilities))
    if missing_capabilities:
        errors.append(f'Required capabilities are unavailable: {", ".join(missing_capabilities)}.')

    profiles = tuple(sorted(set(revision.compatibility_profiles_json or ())))
    if profiles and compatibility_profile not in profiles:
        errors.append('Selected compatibility profile is not allowed by this runbook revision.')

    try:
        adapter = resolver_registry.resolve(revision.resolver_key)
    except Exception as exc:
        errors.append(str(exc))
    else:
        if revision.action_key != getattr(adapter, 'action_key', None):
            errors.append('Runbook action key does not match the registered resolver action.')
        if not callable(getattr(adapter, 'dry_run', None)):
            errors.append('Registered resolver does not implement the mandatory dry-run contract.')
        if not callable(getattr(adapter, 'execute', None)):
            errors.append('Registered resolver does not implement the execution contract.')
        adapter_capabilities = set(getattr(adapter, 'capability_keys', ()) or ())
        unsupported = sorted(set(required_capabilities) - adapter_capabilities)
        if unsupported:
            errors.append(f'Resolver does not declare required capabilities: {", ".join(unsupported)}.')
        adapter_profiles = set(getattr(adapter, 'compatibility_profiles', ()) or ())
        unsupported_profiles = sorted(set(profiles) - adapter_profiles) if profiles else []
        if unsupported_profiles:
            errors.append(f'Resolver does not support compatibility profiles: {", ".join(unsupported_profiles)}.')
        rollback_required = bool(getattr(adapter, 'rollback_required', False))
        if rollback_required and not revision.rollback_json:
            errors.append('Resolver requires rollback metadata before publication.')
        if not rollback_required and not revision.rollback_json:
            warnings.append('Runbook has no rollback metadata; publication reviewer must accept this boundary.')

    if revision.approval_policy == 'allowed' and revision.rollback_json is None:
        errors.append('Automatically allowed runbooks require rollback metadata.')
    if not revision.steps_json:
        errors.append('Published runbooks require at least one executable step.')

    return PublicationValidationResult(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        resolver_action=revision.resolver_key,
        required_capabilities=required_capabilities,
        compatibility_profiles=profiles,
    )
