from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.integrations.registry.providers.harbor.exceptions import HarborConnectionError, HarborResponseError
from app.integrations.registry.providers.harbor.security import (
    _artifact_security_record,
    _normalize_vulnerabilities,
)
from app.integrations.registry.security_contracts import RegistrySecurityTarget


def _target() -> RegistrySecurityTarget:
    return RegistrySecurityTarget(
        artifact_id=42,
        project_name='team',
        repository_name='team/image',
        digest='sha256:abc',
        scan_status='completed',
        scan_completed_at=datetime(2026, 10, 1, tzinfo=UTC),
        vulnerability_summary={'critical': 2},
        signature_status='signed',
        sbom_status='available',
        has_scan_snapshot=True,
    )


@pytest.mark.parametrize('raw', [None, {}, {'vulnerabilities': 'wrong'}, {'vulnerabilities': [42]}])
def test_invalid_report_payload_is_not_a_valid_empty_scan(raw) -> None:
    with pytest.raises(HarborResponseError):
        _normalize_vulnerabilities(raw)


def test_explicit_empty_report_is_valid_observed_zero() -> None:
    findings, summary, _ = _normalize_vulnerabilities({'vulnerabilities': []})
    assert findings == []
    assert summary == {}


@pytest.mark.parametrize('response', ['error', 'invalid'])
def test_changed_scan_report_failure_retains_old_scan_identity_and_findings(response: str) -> None:
    class Client:
        def get_vulnerability_report(self, **_kwargs):
            if response == 'error':
                raise HarborConnectionError('report unavailable')
            return {'invalid': True}

    old = _target()
    evidence, refreshed, reused = _artifact_security_record(
        Client(),
        old,
        {
            'scan_overview': {
                'report': {'scan_status': 'completed', 'end_time': '2026-10-12T00:00:00Z', 'summary': {'critical': 0}}
            }
        },
        project_name='team',
        repository_name='team/image',
    )
    assert evidence.scan_snapshot is None
    assert evidence.vulnerabilities == []
    assert evidence.scan_status == old.scan_status
    assert evidence.scan_completed_at == old.scan_completed_at
    assert evidence.vulnerability_summary == {'critical': 2}
    assert evidence.reuse_existing_scan is True
    assert evidence.provider_metadata['report_error']
    assert (refreshed, reused) == (0, 1)


def test_report_failure_without_prior_snapshot_remains_unavailable() -> None:
    old = _target()
    target = RegistrySecurityTarget(
        artifact_id=old.artifact_id,
        project_name=old.project_name,
        repository_name=old.repository_name,
        digest=old.digest,
        scan_status=None,
        scan_completed_at=None,
        vulnerability_summary={},
        signature_status=None,
        sbom_status=None,
        has_scan_snapshot=False,
    )

    class Client:
        def get_vulnerability_report(self, **_kwargs):
            raise HarborResponseError('invalid report')

    evidence, refreshed, reused = _artifact_security_record(
        Client(),
        target,
        {'scan_overview': {'report': {'scan_status': 'success', 'end_time': '2026-10-12T00:00:00Z'}}},
        project_name='team',
        repository_name='team/image',
    )
    assert evidence.scan_snapshot is None
    assert evidence.scan_status is None
    assert evidence.provider_metadata['report_error']
    assert (refreshed, reused) == (0, 0)
