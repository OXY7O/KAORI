from types import SimpleNamespace

import pytest

from app.knowledge.validation import (
    RunbookValidationError,
    validate_parameter_values,
    validate_publication,
    validate_version_transition,
)
from app.resolver.contracts import DryRunResult, ResolverResult, ResolverResultStatus
from app.resolver.registry import ResolverRegistry


class CompatibleAdapter:
    action_key = 'kubernetes.pod.restart'
    capability_keys = ('kubernetes.pods.patch',)
    compatibility_profiles = ('kubernetes-v1',)
    rollback_required = True

    def dry_run(self, context):
        return DryRunResult(True, 'safe')

    def execute(self, context, dry_run):
        return ResolverResult(ResolverResultStatus.SUCCEEDED, 'done')


def revision(**overrides):
    values = {
        'version': '1.0.0',
        'change_level': 'major',
        'parameter_schema_json': {
            'type': 'object',
            'properties': {'pod_name': {'type': 'string'}},
            'required': ['pod_name'],
            'additionalProperties': False,
        },
        'required_evidence_json': ['cluster_id', 'namespace', 'pod_name'],
        'required_capabilities_json': ['kubernetes.pods.patch'],
        'compatibility_profiles_json': ['kubernetes-v1'],
        'resolver_key': 'kubernetes.pod.restart',
        'action_key': 'kubernetes.pod.restart',
        'rollback_json': {'strategy': 'controller_reconcile'},
        'approval_policy': 'needs_approval',
        'steps_json': [{'type': 'resolver.execute'}],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_publication_accepts_compatible_resolver_contract() -> None:
    registry = ResolverRegistry()
    registry.register(CompatibleAdapter())
    result = validate_publication(
        revision(),
        resolver_registry=registry,
        available_capabilities=('kubernetes.pods.patch',),
        compatibility_profile='kubernetes-v1',
    )
    assert result.valid is True
    assert result.errors == ()


def test_publication_rejects_missing_capability_and_rollback() -> None:
    registry = ResolverRegistry()
    registry.register(CompatibleAdapter())
    result = validate_publication(
        revision(rollback_json=None),
        resolver_registry=registry,
        available_capabilities=(),
        compatibility_profile='kubernetes-v1',
    )
    assert result.valid is False
    assert any('capabilities are unavailable' in error for error in result.errors)
    assert any('requires rollback metadata' in error for error in result.errors)


def test_parameter_values_are_closed_and_typed() -> None:
    schema = revision().parameter_schema_json
    validate_parameter_values(schema, {'pod_name': 'api-123'})
    with pytest.raises(RunbookValidationError, match='Unknown parameters'):
        validate_parameter_values(schema, {'pod_name': 'api-123', 'force': True})
    with pytest.raises(RunbookValidationError, match='must be string'):
        validate_parameter_values(schema, {'pod_name': 123})


def test_semantic_version_transition_is_exact() -> None:
    validate_version_transition(previous_version='1.2.3', candidate_version='1.2.4', change_level='patch')
    with pytest.raises(RunbookValidationError, match='must publish as 1.3.0'):
        validate_version_transition(previous_version='1.2.3', candidate_version='1.4.0', change_level='minor')
