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

    validate(
        'Review cluster health, capacity, alerts, inventory, recommendations, and reporting evidence.',
        owner='compliant',
    )

    with pytest.raises(AssertionError, match='89-96 characters'):
        validate('Too short.', owner='short')

    with pytest.raises(AssertionError, match='89-96 characters'):
        validate(
            'Review this deliberately oversized Hero description because it exceeds the canonical KAORI presentation density and the approved character budget.',
            owner='oversized',
        )

    validate(
        'Review node health, CPU, memory, alerts, configuration, risks, actions, reports, and scope.',
        owner='word-density-advisory',
    )

    with pytest.raises(AssertionError, match='manual line break'):
        validate(
            'Review cluster health, capacity, alerts, inventory, recommendations, and\nreporting evidence.',
            owner='manual-break',
        )


def test_integration_domain_hero_descriptions_are_registered_with_global_budget_audit() -> None:
    namespace = _hero_verifier_namespace()
    descriptions = namespace['_integration_domain_descriptions']()

    assert (
        descriptions['Integration domain Orchestration']
        == 'Connect cluster providers through discovery, connectivity, and governed orchestration workflows.'
    )
    assert set(descriptions) == {
        'Integration domain Orchestration',
        'Integration domain Observability',
        'Integration domain Storage',
    }


def test_cluster_required_blocked_hero_descriptions_are_registered_with_global_budget_audit() -> None:
    namespace = _hero_verifier_namespace()
    descriptions = namespace['_cluster_required_descriptions']()
    values = set(descriptions.values())

    assert 'Validate replacement certificate pairing and coverage before rotating one live TLS Secret.' in values
    assert 'Validate one certificate pair against selected TLS Secrets before controlled rotation in KAORI.' in values
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
