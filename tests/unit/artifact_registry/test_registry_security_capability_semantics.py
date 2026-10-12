from __future__ import annotations

from pathlib import Path

import pytest

from app.artifact_registry.security.presentation import _capability_state


@pytest.mark.parametrize(
    ('supported', 'observed', 'attempted', 'expected'),
    [
        (False, True, True, 'Unsupported'),
        (True, False, False, 'Not Collected'),
        (True, False, True, 'Unavailable'),
        (True, True, True, 'Observed'),
    ],
)
def test_provider_capability_evidence_dimensions_remain_distinct(
    supported: bool, observed: bool, attempted: bool, expected: str,
) -> None:
    assert _capability_state(
        supported=supported, observed=observed, attempted=attempted,
    )['label'] == expected


def test_capability_matrix_does_not_treat_nonnull_unknown_status_as_usable() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'app/artifact_registry/security/presentation.py').read_text()
    matrix = source.split('def _security_source_capabilities(', 1)[1].split(
        'def _security_vulnerability_page(', 1
    )[0]
    assert "RegistryArtifact.signature_status) == 'signed'" in matrix
    assert "RegistryArtifact.sbom_status) == 'available'" in matrix
    assert 'RegistryArtifact.scan_snapshots.any(' in matrix
    assert "RegistryArtifact.scan_status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES)" in matrix
    assert "observed=bool(scan_ready)" in matrix
    assert "attempted=bool(scan_attempted)" in matrix
    assert "'coverage': {" in matrix
    scope = source.split('def _security_scope_evidence(', 1)[1].split(
        'def _security_source_capabilities(', 1
    )[0]
    assert "RegistryProject.integration_instance_id.in_(signature_ids)" in scope
    assert "RegistryProject.integration_instance_id.in_(sbom_ids)" in scope


def test_capability_table_surfaces_partial_numerator_and_denominator() -> None:
    template = (
        Path(__file__).resolve().parents[3] /
        'app/templates/artifact_registry/partials/_security_workspace.html'
    ).read_text()
    for key in ('vulnerability', 'signature', 'sbom'):
        assert 'row.coverage.' + key in template
        assert 'row.artifact_count' in template


def test_partially_usable_capability_is_not_presented_as_fully_observed() -> None:
    assert _capability_state(
        supported=True, observed=True, attempted=True,
        observed_count=1, artifact_total=100,
    ) == {'key': 'supported_partial', 'label': 'Partial', 'tone': 'warning'}
    assert _capability_state(
        supported=True, observed=True, attempted=True,
        observed_count=100, artifact_total=100,
    )['label'] == 'Observed'
