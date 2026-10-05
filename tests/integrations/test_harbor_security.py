from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.artifact_registry.security.contracts import RegistrySecurityTarget
from app.integrations.registry.providers.harbor.exceptions import (
    HarborAuthError,
    HarborConnectionError,
)
from app.integrations.registry.providers.harbor import security as harbor_security


@dataclass
class _Instance:
    timeout: int = 5


def _target(
    artifact_id: int,
    *,
    repository: str,
    digest: str,
    has_scan_snapshot: bool = False,
) -> RegistrySecurityTarget:
    return RegistrySecurityTarget(
        artifact_id=artifact_id,
        project_name='base',
        repository_name=repository,
        digest=digest,
        scan_status='success' if has_scan_snapshot else None,
        scan_completed_at=None,
        vulnerability_summary={'high': 1} if has_scan_snapshot else {},
        signature_status='signed' if has_scan_snapshot else None,
        sbom_status='available' if has_scan_snapshot else None,
        has_scan_snapshot=has_scan_snapshot,
    )


def test_harbor_security_retries_enriched_discovery_with_smaller_page(monkeypatch) -> None:
    page_sizes: list[int] = []

    class _Client:
        def list_all_artifacts(self, **kwargs):
            page_sizes.append(int(kwargs['page_size']))
            if kwargs['page_size'] == 20:
                raise HarborConnectionError('transient enriched page timeout')
            return [{'digest': 'sha256:a'}]

    monkeypatch.setattr(
        harbor_security,
        'build_client',
        lambda _instance, **_kwargs: _Client(),
    )

    evidence = harbor_security.collect_harbor_security(
        _Instance(),
        [_target(1, repository='filebeat', digest='sha256:a')],
    )

    assert page_sizes == [20, 10]
    assert evidence.provider_metadata['successful_repository_count'] == 1
    assert evidence.provider_metadata['repository_failure_count'] == 0
    assert evidence.provider_metadata['security_discovery_page_sizes'] == [20, 10]


def test_harbor_security_isolates_one_repository_transport_failure(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    class _Client:
        def list_all_artifacts(self, **kwargs):
            repository = str(kwargs['repository_name'])
            page_size = int(kwargs['page_size'])
            calls.append((repository, page_size))
            if repository == 'slow':
                raise HarborConnectionError('transient enriched page timeout')
            return [{'digest': 'sha256:ok'}]

    monkeypatch.setattr(
        harbor_security,
        'build_client',
        lambda _instance, **_kwargs: _Client(),
    )

    evidence = harbor_security.collect_harbor_security(
        _Instance(),
        [
            _target(1, repository='slow', digest='sha256:slow', has_scan_snapshot=True),
            _target(2, repository='healthy', digest='sha256:ok'),
        ],
    )

    assert ('slow', 20) in calls
    assert ('slow', 10) in calls
    assert evidence.provider_metadata['successful_repository_count'] == 1
    assert evidence.provider_metadata['repository_failure_count'] == 1
    failure = evidence.provider_metadata['repository_failures'][0]
    assert failure['project_name'] == 'base'
    assert failure['repository_name'] == 'slow'
    retained = next(item for item in evidence.artifacts if item.artifact_id == 1)
    assert retained.reuse_existing_scan is True
    assert retained.scan_status == 'success'
    assert retained.provider_metadata['provider_evidence'] == 'repository_security_refresh_unavailable'


def test_harbor_security_fails_provider_when_every_repository_is_unavailable(monkeypatch) -> None:
    class _Client:
        def list_all_artifacts(self, **_kwargs):
            raise HarborConnectionError('provider unavailable')

    monkeypatch.setattr(
        harbor_security,
        'build_client',
        lambda _instance, **_kwargs: _Client(),
    )

    with pytest.raises(HarborConnectionError) as exc_info:
        harbor_security.collect_harbor_security(
            _Instance(),
            [_target(1, repository='slow', digest='sha256:slow', has_scan_snapshot=True)],
        )

    assert 'every committed repository' in str(exc_info.value)


def test_harbor_security_keeps_authentication_failure_fail_fast(monkeypatch) -> None:
    page_sizes: list[int] = []

    class _Client:
        def list_all_artifacts(self, **kwargs):
            page_sizes.append(int(kwargs['page_size']))
            raise HarborAuthError('Harbor authentication or authorization failed with HTTP 401.', status=401)

    monkeypatch.setattr(
        harbor_security,
        'build_client',
        lambda _instance, **_kwargs: _Client(),
    )

    with pytest.raises(HarborAuthError):
        harbor_security.collect_harbor_security(
            _Instance(),
            [_target(1, repository='filebeat', digest='sha256:a')],
        )

    assert page_sizes == [20]
