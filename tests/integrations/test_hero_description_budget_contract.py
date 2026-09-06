from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _hero_verifier_namespace() -> dict[str, object]:
    return runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))


def test_hero_description_budget_enforces_target_and_hard_boundary() -> None:
    namespace = _hero_verifier_namespace()
    validate = namespace['_validate_description_budget']

    validate('Review cluster posture, readiness, evidence, and operational context.', owner='compliant')

    with pytest.raises(AssertionError, match='7-12 words'):
        validate('Too short.', owner='short')

    with pytest.raises(AssertionError, match='hard maximum 16 words'):
        validate(
            'Review this deliberately oversized Hero description because it contains far too many words for the canonical KAORI surface today.',
            owner='oversized',
        )


def test_integration_domain_hero_descriptions_are_registered_with_global_budget_audit() -> None:
    namespace = _hero_verifier_namespace()
    descriptions = namespace['_integration_domain_hero_descriptions']()

    assert (
        descriptions['Orchestration'] == 'Cluster providers, control-plane access, discovery, and runtime connectivity.'
    )
    assert set(descriptions) == {'Orchestration', 'Observability', 'Storage'}


def test_cluster_required_blocked_hero_descriptions_are_registered_with_global_budget_audit() -> None:
    namespace = _hero_verifier_namespace()
    descriptions = namespace['_cluster_required_hero_descriptions']()
    values = set(descriptions.values())

    assert 'Validate replacement certificate pairing and coverage before rotating one live TLS Secret.' in values
    assert 'Validate one certificate pair against selected TLS Secrets before controlled rotation.' in values
    assert (
        'Validate replacement certificate material, key matching, and target coverage before rotating one live TLS Secret.'
        not in values
    )
    assert (
        'Validate one certificate and private-key pair against explicitly selected TLS Secrets before any controlled bulk rotation.'
        not in values
    )


def test_global_hero_verifier_covers_blocked_route_description_budget() -> None:
    namespace = _hero_verifier_namespace()
    namespace['verify']()
