"""Provider-neutral Secrets & PKI UI and committed readiness contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.common.workspace_navigation import _active_capability_key, _workspace_key
from app.common.workspace_navigation_catalog import WORKSPACES
from app.secrets_pki import presentation


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def limit(self, value):
        return _Query(self.rows[:value])

    def all(self):
        return self.rows


def _source(index, mounts=('secret',), namespace=''):
    return SimpleNamespace(
        id=index,
        integration_instance_id=index,
        namespace=namespace,
        kv2_mounts=list(mounts),
    )


def _state(index, mount='secret', *, count=0, status='ready', committed=True, namespace=''):
    return SimpleNamespace(
        integration_instance_id=index,
        mount=mount,
        provider_namespace=namespace,
        observed_count=count,
        status=status,
        last_committed_at=datetime(2026, 10, 22, tzinfo=UTC) if committed else None,
    )


def _patch_sources(monkeypatch, sources, states):
    monkeypatch.setattr(
        presentation,
        'VaultInstance',
        SimpleNamespace(id=SimpleNamespace(asc=lambda: None), integration_instance=object(), query=_Query(sources)),
    )
    monkeypatch.setattr(
        presentation,
        'SecretInventoryCollectionState',
        SimpleNamespace(
            integration_instance_id=SimpleNamespace(in_=lambda _ids: None),
            provider_namespace=None,
            mount=None,
            query=_Query(states),
        ),
    )


def test_secrets_pki_workspace_follows_canonical_sidebar_navigation():
    workspace = next(item for item in WORKSPACES if item.key == 'secrets_pki')
    assert workspace.label == 'Secrets & PKI'
    assert workspace.section == 'Infrastructure'
    assert [(item.key, item.endpoint) for item in workspace.capabilities] == [
        ('overview', 'secrets_pki.overview'),
        ('inventory', 'secrets_pki.inventory'),
        ('lifecycle', 'secrets_pki.lifecycle'),
    ]
    assert all(item.permissions == ('secrets_pki.view',) for item in workspace.capabilities)
    assert _workspace_key('secrets_pki.overview') == 'secrets_pki'
    assert _workspace_key('secrets_pki.inventory') == 'secrets_pki'
    assert _workspace_key('secrets_pki.lifecycle') == 'secrets_pki'
    assert _active_capability_key('secrets_pki', 'secrets_pki.lifecycle') == 'lifecycle'
    assert _active_capability_key('secrets_pki', 'secrets_pki.inventory') == 'inventory'


def test_zero_without_committed_evidence_is_not_reported_as_a_healthy_zero(monkeypatch):
    _patch_sources(monkeypatch, [_source(1)], [])
    summary = presentation.build_secrets_pki_operational_summary()
    assert summary['state'] == 'not_collected'
    assert summary['observed_secret_count'] is None
    assert summary['committed_mount_count'] == 0
    assert summary['has_evidence'] is False


def test_genuine_committed_zero_is_supported(monkeypatch):
    _patch_sources(monkeypatch, [_source(1)], [_state(1, count=0)])
    summary = presentation.build_secrets_pki_operational_summary()
    assert summary['state'] == 'committed'
    assert summary['observed_secret_count'] == 0
    assert summary['has_evidence'] is True
    assert summary['approved_mount_count'] == 1
    assert summary['committed_mount_count'] == 1


def test_partial_or_stale_observation_does_not_claim_complete_readiness(monkeypatch):
    sources = [_source(1, mounts=('secret', 'team-kv'))]
    _patch_sources(monkeypatch, sources, [_state(1, count=2)])
    partial = presentation.build_secrets_pki_operational_summary()
    assert partial['state'] == 'partial'
    assert partial['observed_secret_count'] == 2
    _patch_sources(monkeypatch, sources, [_state(1, count=2, status='stale')])
    stale = presentation.build_secrets_pki_operational_summary()
    assert stale['state'] == 'stale'
    assert stale['has_evidence']


def test_retired_mount_history_is_excluded_from_active_inventory_counts(monkeypatch):
    _patch_sources(
        monkeypatch,
        [_source(1)],
        [
            _state(1, count=1),
            _state(1, mount='retired', count=800),
        ],
    )
    summary = presentation.build_secrets_pki_operational_summary()
    assert summary['observed_secret_count'] == 1


def test_oversized_fleet_is_blocked_not_partially_summarized(monkeypatch):
    _patch_sources(
        monkeypatch,
        [_source(index) for index in range(presentation.MAX_FLEET_SOURCES + 1)],
        [],
    )
    summary = presentation.build_secrets_pki_operational_summary()
    assert summary['source_limit_exceeded'] is True
    assert summary['has_evidence'] is False
    assert summary['observed_secret_count'] is None
