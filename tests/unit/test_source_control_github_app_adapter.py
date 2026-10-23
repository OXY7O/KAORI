"""SC-02 distinguishes connection probe, Full Validation and Runtime Refresh."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import adapter
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubProviderError, InstallationReadiness,
)


def _instance():
    canonical = SimpleNamespace(
        name='GitHub team', integration_type='source_control',
        readiness_status='validation_required', health_status=None,
        metadata_json={'provider_label': 'GitHub'}, last_error=None,
        last_checked_at=None, lifecycle_status='active', enabled=True,
    )
    return SimpleNamespace(
        id=70, integration_instance=canonical,
        native_installation_id='11', account=SimpleNamespace(native_account_id='22'),
        repository_scope='unknown', last_observed_at=None,
    )


def _evidence(permissions=('metadata', 'contents')):
    return InstallationReadiness(
        app_id=2, installation_id=11, account_id=22,
        account_type='Organization', repository_selection='selected',
        granted_repository_count=3, permission_names=permissions,
        observed_at=datetime.now(UTC),
    )


@pytest.fixture
def frozen_db(monkeypatch):
    recorded = []
    monkeypatch.setattr(adapter, 'db', SimpleNamespace(session=SimpleNamespace(
        commit=lambda: recorded.append('commit')
    )))
    monkeypatch.setattr(adapter, '_canonical', lambda i: i.integration_instance)
    return recorded


def test_test_connection_does_not_persist_or_claim_ready(monkeypatch, frozen_db):
    instance = _instance()
    monkeypatch.setattr(adapter, 'probe_installation', lambda i: _evidence())
    result = adapter.runtime_adapter.execute('connection.test', instance)
    assert result['connected'] is True
    assert frozen_db == []
    assert instance.integration_instance.readiness_status == 'validation_required'
    assert 'token' not in repr(result).lower()


def test_full_validation_marks_connection_ready_but_not_other_capabilities(monkeypatch, frozen_db):
    instance = _instance()
    monkeypatch.setattr(adapter, 'probe_installation', lambda i: _evidence())
    result = adapter.runtime_adapter.execute('runtime.validate', instance)
    assert result['connected'] is True
    assert result['readiness_status'] == 'ready'
    assert result['capabilities']['source_revision'] == 'permission_verified'
    assert result['capabilities']['workflow_runs'] == 'permission_unavailable'
    assert instance.integration_instance.metadata_json['github_validation']['grant_count_hint'] == 3
    assert frozen_db == ['commit']


def test_full_validation_fail_closed_with_safe_error(monkeypatch, frozen_db):
    instance = _instance()
    def error(_instance):
        raise GitHubProviderError('redacted provider error')
    monkeypatch.setattr(adapter, 'probe_installation', error)
    result = adapter.runtime_adapter.refresh(instance)
    assert result['connected'] is False
    assert result['readiness_status'] == 'blocked'
    assert instance.integration_instance.health_status == 'unhealthy'
    assert 'redacted provider error' not in repr(result)
    assert frozen_db == ['commit']


def test_runtime_refresh_preserves_capability_observation(monkeypatch, frozen_db):
    instance = _instance()
    scope = {'profile': 'github-app-readiness-v1', 'repository_scope': 'selected'}
    instance.integration_instance.metadata_json['github_validation'] = scope
    monkeypatch.setattr(adapter, 'build_client_for_installation',
                        lambda i: SimpleNamespace(installation_detail=lambda *_: {'id': 11}))
    result = adapter.runtime_adapter.refresh_health(instance)
    assert result['health_status'] == 'healthy'
    assert instance.integration_instance.metadata_json['github_validation'] == scope
    assert instance.integration_instance.readiness_status == 'validation_required'
    assert frozen_db == ['commit']


def test_runtime_refresh_revocation_blocks_readiness(monkeypatch, frozen_db):
    instance = _instance()
    def invalid(*args):
        raise GitHubProviderError('revoked')
    monkeypatch.setattr(adapter, 'build_client_for_installation',
                        lambda i: SimpleNamespace(installation_detail=invalid))
    result = adapter.runtime_adapter.refresh_health(instance)
    assert result['health_status'] == 'unhealthy'
    assert instance.integration_instance.readiness_status == 'blocked'


def test_adapter_not_registered_or_advertised_available():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    kernel = (root / 'app/integrations/kernel/registry.py').read_text()
    source = (root / 'app/integrations/source_control/source_control/providers/github/__init__.py').read_text()
    matrix = (root / 'app/definitions/catalogs/integrations/provider_matrix.yaml').read_text()
    assert "if provider_kind('source_control', 'github').available:" in kernel
    assert 'registry.register(' not in source
    assert 'lifecycle: planned' in matrix.split('- key: source_control')[-1]
