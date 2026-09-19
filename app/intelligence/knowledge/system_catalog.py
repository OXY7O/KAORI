from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple, unique_by


@dataclass(frozen=True)
class SystemRunbookDefinition:
    """Validated source-controlled KAORI runbook contract."""

    runbook_key: str
    title: str
    description: str
    domain: str
    asset_kind: str
    version: str
    action_key: str
    resolver_key: str
    approval_policy: str
    maturity: str
    validation_status: str
    verification_summary: str
    recovery_summary: str
    required_evidence: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    compatibility_profiles: tuple[str, ...]
    change_level: str
    parameter_schema: dict[str, Any]
    steps: tuple[dict[str, Any], ...]
    recovery: dict[str, Any] | None
    default_evidence_mapping: dict[str, str]

    def revision_payload(self) -> dict[str, Any]:
        return {
            'runbook_key': self.runbook_key,
            'version': self.version,
            'action_key': self.action_key,
            'resolver_key': self.resolver_key,
            'approval_policy': self.approval_policy,
            'required_evidence': sorted(self.required_evidence),
            'required_capabilities': sorted(self.required_capabilities),
            'compatibility_profiles': sorted(self.compatibility_profiles),
            'change_level': self.change_level,
            'parameter_schema': dict(self.parameter_schema),
            'steps': [dict(step) for step in self.steps],
            'rollback': dict(self.recovery) if self.recovery else None,
        }

    @property
    def content_hash(self) -> str:
        encoded = json.dumps(
            self.revision_payload(),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
        ).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


def _load_system_runbooks() -> tuple[SystemRunbookDefinition, ...]:
    document = load_definition_document('intelligence/knowledge/system_runbooks.yaml', expected_kind='system_runbooks')
    raw_items = [
        require_mapping(item, f'runbooks[{index}]')
        for index, item in enumerate(require_list(document.get('runbooks'), 'runbooks'))
    ]
    unique_by(raw_items, 'runbook_key', 'runbooks')
    output: list[SystemRunbookDefinition] = []
    for index, raw in enumerate(raw_items):
        path = f'runbooks[{index}]'
        parameter_schema = require_mapping(raw.get('parameter_schema'), f'{path}.parameter_schema')
        raw_steps = require_list(raw.get('steps'), f'{path}.steps')
        steps = tuple(
            dict(require_mapping(step, f'{path}.steps[{step_index}]')) for step_index, step in enumerate(raw_steps)
        )
        recovery_raw = raw.get('recovery')
        recovery = dict(require_mapping(recovery_raw, f'{path}.recovery')) if recovery_raw is not None else None
        evidence_mapping_raw = require_mapping(
            raw.get('default_evidence_mapping', {}),
            f'{path}.default_evidence_mapping',
        )
        evidence_mapping: dict[str, str] = {}
        for key, value in evidence_mapping_raw.items():
            if not isinstance(key, str) or not isinstance(value, str) or not key.strip() or not value.strip():
                raise DefinitionError(f'{path}.default_evidence_mapping requires non-empty string keys and values.')
            evidence_mapping[key.strip()] = value.strip()
        output.append(
            SystemRunbookDefinition(
                runbook_key=require_str(raw, 'runbook_key', path),
                title=require_str(raw, 'title', path),
                description=require_str(raw, 'description', path),
                domain=require_str(raw, 'domain', path),
                asset_kind=require_str(raw, 'asset_kind', path),
                version=require_str(raw, 'version', path),
                action_key=require_str(raw, 'action_key', path),
                resolver_key=require_str(raw, 'resolver_key', path),
                approval_policy=require_str(raw, 'approval_policy', path),
                maturity=require_str(raw, 'maturity', path),
                validation_status=require_str(raw, 'validation_status', path),
                verification_summary=require_str(raw, 'verification_summary', path),
                recovery_summary=require_str(raw, 'recovery_summary', path),
                required_evidence=string_tuple(raw.get('required_evidence'), f'{path}.required_evidence'),
                required_capabilities=string_tuple(raw.get('required_capabilities'), f'{path}.required_capabilities'),
                compatibility_profiles=string_tuple(
                    raw.get('compatibility_profiles'), f'{path}.compatibility_profiles'
                ),
                change_level=require_str(raw, 'change_level', path),
                parameter_schema=dict(parameter_schema),
                steps=steps,
                recovery=recovery,
                default_evidence_mapping=evidence_mapping,
            )
        )
    return tuple(output)


SYSTEM_RUNBOOK_CATALOG = _load_system_runbooks()
SYSTEM_RUNBOOK_KEYS = frozenset(item.runbook_key for item in SYSTEM_RUNBOOK_CATALOG)


def list_system_runbooks() -> tuple[SystemRunbookDefinition, ...]:
    return SYSTEM_RUNBOOK_CATALOG


def get_system_runbook(runbook_key: str) -> SystemRunbookDefinition | None:
    normalized = str(runbook_key or '').strip()
    return next((item for item in SYSTEM_RUNBOOK_CATALOG if item.runbook_key == normalized), None)


def is_system_runbook_key(runbook_key: str) -> bool:
    return str(runbook_key or '').strip() in SYSTEM_RUNBOOK_KEYS
