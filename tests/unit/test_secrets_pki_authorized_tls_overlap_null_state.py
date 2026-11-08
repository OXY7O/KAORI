"""Only separately authorized committed public TLS overlap contributes metrics."""

from __future__ import annotations

import pytest

from app.secrets_pki import operational_evidence_workspaces as workspace


def _metric_value(result: dict, label: str) -> int | None:
    return next(metric['value'] for metric in result['metrics'] if metric['label'] == label)


def test_unauthorized_secret_consumer_workspace_does_not_read_tls_source(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_read(**_kwargs: object) -> None:
        pytest.fail('unauthorized workspace must never access separate TLS governance evidence')

    monkeypatch.setattr(workspace, 'build_certificate_delivery_overlap', forbidden_read)
    result = workspace.build_operational_evidence_workspace(kind='consumers', can_view_kubernetes_tls=False)

    assert _metric_value(result, 'Observed Public TLS Overlap') is None
    assert _metric_value(result, 'TLS Secrets Matched') is None
    assert result['source_rows'][1]['status'] == 'Additional TLS Permission Required'


@pytest.mark.parametrize(
    ('evidence', 'count'),
    [
        (None, None),
        ({'status': 'partial', 'overlapping_certificates': 2, 'matching_kubernetes_tls_secrets': 4}, None),
        ({'status': 'no_overlap_observed', 'overlapping_certificates': 0, 'matching_kubernetes_tls_secrets': 0}, 0),
        ({'status': 'overlap_observed', 'overlapping_certificates': 2, 'matching_kubernetes_tls_secrets': 4}, 2),
    ],
)
def test_authorized_overlap_requires_committed_qualified_observation(
    monkeypatch: pytest.MonkeyPatch, evidence: dict | None, count: int | None
) -> None:
    monkeypatch.setattr(workspace, 'build_certificate_delivery_overlap', lambda **_kwargs: evidence)
    result = workspace.build_operational_evidence_workspace(kind='consumers', can_view_kubernetes_tls=True)

    assert _metric_value(result, 'Observed Public TLS Overlap') == count
    expected_secrets = 4 if count == 2 else count
    assert _metric_value(result, 'TLS Secrets Matched') == expected_secrets
    assert _metric_value(result, 'Confirmed Secret Consumers') is None
    assert _metric_value(result, 'Verified Rotation Cutovers') is None
