"""Synthetic candidate review only; no native remote execution or worker admission."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.infrastructure_automation import remote_preflight_source, remote_worker_review
from app.infrastructure_automation.kubernetes.source_policy import SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_facts import RemoteFactsTarget, normalize_remote_facts
from app.infrastructure_automation.remote_preflight_target import RemoteTargetReview
from app.infrastructure_automation.source import AutomationPilotDenied
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import canonical_statement

_NOW = datetime(2026, 11, 28, 1, tzinfo=UTC)
_TARGETS = tuple(
    RemoteFactsTarget(f'kaori-{index}', f'00000000-0000-4000-8000-{index:012d}', role)
    for index, role in enumerate(('control_plane', 'worker', 'worker'), start=1)
)


@pytest.fixture
def source_store(tmp_path, monkeypatch):
    module = remote_preflight_source
    for filename in module._EXPECTED_BLOBS:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}', encoding='utf-8')
    (tmp_path / module.REMOTE_MANIFEST).write_bytes(canonical_statement(module._EXPECTED_MANIFEST))
    replies = {
        ('rev-parse', '--show-toplevel'): str(tmp_path),
        ('remote', 'get-url', 'origin'): 'https://github.com/OXY7O/kaori-operations.git',
        ('rev-parse', 'HEAD'): module.REMOTE_CANDIDATE_SHA,
        ('status', '--porcelain', '--untracked-files=all'): '',
    }
    replies.update({('hash-object', path): blob for path, blob in module._EXPECTED_BLOBS.items()})
    monkeypatch.setattr(module, '_git', lambda root, *args: replies[args])
    return tmp_path, replies


def test_exact_disabled_source_candidate_remains_non_authorizing(source_store):
    path, _ = source_store
    review = remote_preflight_source.review_remote_source_candidate(str(path))
    assert review.revision == remote_preflight_source.REMOTE_CANDIDATE_SHA
    assert len(review.fingerprint) == 64
    assert review.execution_authorized is False


@pytest.mark.parametrize(
    ('args', 'value'),
    [
        (('remote', 'get-url', 'origin'), 'https://other.invalid/operations.git'),
        (('rev-parse', 'HEAD'), 'a' * 40),
        (('status', '--porcelain', '--untracked-files=all'), ' M ansible/ansible.cfg'),
        (('hash-object', remote_preflight_source.REMOTE_PLAYBOOK), 'a' * 40),
    ],
)
def test_source_identity_drift_denies(source_store, args, value):
    path, replies = source_store
    replies[args] = value
    with pytest.raises(AutomationPilotDenied):
        remote_preflight_source.review_remote_source_candidate(str(path))


@pytest.mark.parametrize('changes', [{'execution_enabled': True}, {'schema_version': True}, {'become': True}])
def test_manifest_cannot_enable_execution_even_if_blob_check_is_mocked(source_store, changes):
    path, _ = source_store
    manifest = remote_preflight_source._EXPECTED_MANIFEST | changes
    (path / remote_preflight_source.REMOTE_MANIFEST).write_bytes(canonical_statement(manifest))
    with pytest.raises(AutomationPilotDenied):
        remote_preflight_source.review_remote_source_candidate(str(path))


def _facts():
    return {
        'ansible_distribution': 'Ubuntu',
        'ansible_distribution_version': '24.04',
        'ansible_distribution_major_version': '24',
        'ansible_kernel': '6.8.0-41-generic',
        'ansible_architecture': 'x86_64',
        'ansible_pkg_mgr': 'apt',
        'ansible_python_version': '3.12.3',
        'ansible_processor_vcpus': 4,
        'ansible_memtotal_mb': 8192,
        'ansible_effective_user_id': 1000,
        'ansible_mounts': [{'mount': '/', 'size_total': 80 * 1024**3, 'size_available': 60 * 1024**3}],
        'ansible_default_ipv4': {'address': '192.0.2.1'},
        'ansible_date_time': {'epoch': '123'},
        'ignored_fixture': 'must-not-be-projected',
    }


def _events():
    return [
        {
            'event': 'runner_on_ok',
            'event_data': {
                'host': target.alias,
                'task_action': 'ansible.builtin.setup',
                'res': {'changed': False, 'ansible_facts': _facts()},
            },
        }
        for target in _TARGETS
    ]


def _stats():
    return {'ok': {target.alias: 1 for target in _TARGETS}, 'changed': {}}


def test_bounded_remote_facts_do_not_claim_full_preflight():
    result = normalize_remote_facts(_TARGETS, events=_events(), stats=_stats())
    assert len(result.hosts) == 3
    assert all(host.os_supported and host.capacity_sufficient for host in result.hosts)
    summary = result.committed_summary()
    assert summary['full_preflight_verified'] is False
    assert summary['execution_authorized'] is False
    assert '192.0.2.1' not in str(summary)
    assert 'must-not-be-projected' not in str(summary)
    assert 'host_keys_verified' not in summary
    assert 'privileged_identity_verified' not in summary
    assert 'attestation' not in summary


@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'foreign', 'changed', 'other_action', 'unreachable'])
def test_remote_facts_denies_missing_changed_or_unexpected_events(failure):
    events = _events()
    if failure == 'missing':
        events.pop()
    elif failure == 'duplicate':
        events.append(events[0])
    elif failure == 'foreign':
        events[0]['event_data']['host'] = 'localhost'
    elif failure == 'changed':
        events[0]['event_data']['res']['changed'] = True
    elif failure == 'other_action':
        events[0]['event_data']['task_action'] = 'shell'
    else:
        events.append({'event': 'runner_on_unreachable'})
    with pytest.raises(AutomationPilotDenied):
        normalize_remote_facts(_TARGETS, events=events, stats=_stats())


@pytest.mark.parametrize(
    'changes',
    [
        {'ok': {'kaori-1': 1}},
        {'ok': {'kaori-1': True, 'kaori-2': 1, 'kaori-3': 1}},
        {'changed': {'kaori-1': 1}},
        {'failures': {'kaori-2': 1}},
        {'dark': {'localhost': 0}},
        {'skipped': {'kaori-3': 1}},
    ],
)
def test_recap_drift_denies(changes):
    with pytest.raises(AutomationPilotDenied):
        normalize_remote_facts(_TARGETS, events=_events(), stats=_stats() | changes)


def test_unsupported_or_small_host_is_reported_not_promoted():
    events = _events()
    facts = events[0]['event_data']['res']['ansible_facts']
    facts.update(ansible_distribution='Debian', ansible_distribution_version='12', ansible_processor_vcpus=1)
    result = normalize_remote_facts(_TARGETS, events=events, stats=_stats())
    assert result.hosts[0].os_supported is False
    assert result.hosts[0].capacity_sufficient is False


@pytest.fixture
def worker_store(monkeypatch):
    source = remote_preflight_source.RemoteSourceReview(remote_preflight_source.REMOTE_CANDIDATE_SHA, 'a' * 64)
    target = RemoteTargetReview(
        1, 2, SOURCE_CANDIDATE_SHA, 'sha256:' + 'c' * 64, 'd' * 64, 'e' * 64, 'f' * 64,
        _TARGETS, _NOW + timedelta(minutes=15),
    )
    selector = remote_worker_review.worker_review_selector(source, target, worker_identity='automation@fixture')
    payload = {
        'schema': 'kaori.automation.remote_worker_review.v1',
        'state': 'active',
        'selector': selector,
        'provenance_evidence_ref': '1' * 64,
        'target_authority_ref': '2' * 64,
        'reviewer_id': 3,
        'issued_at': _NOW.isoformat(),
        'expires_at': (_NOW + timedelta(minutes=5)).isoformat(),
    }
    root = Ed25519PrivateKey.generate()

    def envelope(fields, signer=root):
        return canonical_statement({'payload': fields, 'signature': signer.sign(canonical_statement(fields)).hex()})

    name = 'worker-' + sha256(canonical_statement(selector)).hexdigest() + '.json'
    files = {'root.pub': root.public_key().public_bytes_raw().hex().encode('ascii'), name: envelope(payload)}
    monkeypatch.setattr(remote_worker_review, '_read_worker_file', files.get)
    return source, target, files, name, payload, envelope


def test_worker_receipt_requires_signature_and_is_not_execution_authority(worker_store):
    source, target, files, name, payload, envelope = worker_store
    resolve = remote_worker_review.resolve_remote_worker_review
    result = resolve(source, target, worker_identity='automation@fixture', now=_NOW)
    assert result is not None
    assert result.execution_authorized is False
    files[name] = envelope(payload, Ed25519PrivateKey.generate())
    assert resolve(source, target, worker_identity='automation@fixture', now=_NOW) is None
    files[name] = envelope(payload)
    del files[name]
    assert resolve(source, target, worker_identity='automation@fixture', now=_NOW) is None


@pytest.mark.parametrize(
    'changes',
    [
        {'state': 'revoked'},
        {'reviewer_id': 2},
        {'reviewer_id': True},
        {'provenance_evidence_ref': 'not-verified'},
        {'target_authority_ref': ''},
        {'expires_at': (_NOW + timedelta(minutes=16)).isoformat()},
        {'issued_at': (_NOW + timedelta(seconds=1)).isoformat()},
    ],
)
def test_signed_worker_review_cannot_override_exact_scope(worker_store, changes):
    source, target, files, name, payload, envelope = worker_store
    files[name] = envelope(payload | changes)
    assert remote_worker_review.resolve_remote_worker_review(
        source, target, worker_identity='automation@fixture', now=_NOW
    ) is None


def test_worker_receipt_cannot_transfer_to_changed_target_or_worker(worker_store):
    source, target, files, name, _, _ = worker_store
    for changed, worker in (
        (replace(target, actor_id=9), 'automation@fixture'),
        (replace(target, source_sha='b' * 40), 'automation@fixture'),
        (replace(target, ee_digest='sha256:' + '9' * 64), 'automation@fixture'),
        (replace(target, access_fingerprint='9' * 64), 'automation@fixture'),
        (target, 'automation@other'),
    ):
        selector = remote_worker_review.worker_review_selector(source, changed, worker_identity=worker)
        files['worker-' + sha256(canonical_statement(selector)).hexdigest() + '.json'] = files[name]
        assert remote_worker_review.resolve_remote_worker_review(
            source, changed, worker_identity=worker, now=_NOW
        ) is None
