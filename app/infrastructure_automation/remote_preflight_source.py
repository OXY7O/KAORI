"""Exact disabled remote preflight source candidate (#5186).

Review-only. The accepted Kubespray profile and localhost pilot pins remain
unchanged. A clean candidate checkout does not admit remote execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure_automation.source import AutomationPilotDenied, _git, _source_file

REMOTE_CANDIDATE_SHA = '9e2ca3e636a0d088eddc195fefe8733f5eee979a'
REMOTE_OPERATION = 'linux.remote_preflight.v1'
REMOTE_PLAYBOOK = 'ansible/playbooks/linux_remote_preflight.yml'
REMOTE_MANIFEST = 'automation/remote_preflight_candidate.json'
REMOTE_GROUP = 'kaori_remote_pilot'

_ALLOWED_ORIGINS = frozenset({
    'https://github.com/OXY7O/kaori-operations.git',
    'https://github.com/OXY7O/kaori-operations',
    'git@github.com:OXY7O/kaori-operations.git',
})
_EXPECTED_BLOBS = {
    REMOTE_PLAYBOOK: '0a7882fa033c92cc87dcffbbd45f0beb15fc396a',
    REMOTE_MANIFEST: '103972e2bc91d6aff70f154f29c3f532bb1e26d1',
    'ansible/ansible.cfg': '8373b2c91bc416cfd46c10069d12780d78e48f91',
    'execution-environments/requirements.txt': '1765812c981fc4bca9acd782a4f6584c7ce0e8bb',
}
_EXPECTED_MANIFEST = {
    'schema_version': 1,
    'kind': 'remote_read_only_source_candidate',
    'operation': REMOTE_OPERATION,
    'playbook': REMOTE_PLAYBOOK,
    'mode': 'read_only',
    'become': False,
    'execution_enabled': False,
    'mutation_authorized': False,
    'inventory': 'canonical_kaori_worker_generated',
    'limit': REMOTE_GROUP,
    'target': {
        'environment': 'nonproduction',
        'allocation': 'existing_linux_hosts',
        'control_plane_count': 1,
        'worker_count': 2,
    },
    'facts_contract': 'linux.remote_preflight.facts.v1',
}


@dataclass(frozen=True, slots=True)
class RemoteSourceReview:
    revision: str
    fingerprint: str
    execution_authorized: bool = False


def review_remote_source_candidate(source_path: str) -> RemoteSourceReview:
    """Check exact candidate Git identity and reviewed blobs; never run Ansible."""
    try:
        root = Path(source_path).resolve(strict=True)
        if not root.is_dir() or _git(root, 'rev-parse', '--show-toplevel') != str(root):
            raise AutomationPilotDenied('Remote review source is not an exact Git root')
        if _git(root, 'remote', 'get-url', 'origin') not in _ALLOWED_ORIGINS:
            raise AutomationPilotDenied('Remote review source origin is unqualified')
        if _git(root, 'rev-parse', 'HEAD') != REMOTE_CANDIDATE_SHA:
            raise AutomationPilotDenied('Remote review source revision is unqualified')
        if _git(root, 'status', '--porcelain', '--untracked-files=all'):
            raise AutomationPilotDenied('Remote review source contains uncommitted changes')
        for filename, expected_blob in _EXPECTED_BLOBS.items():
            path = _source_file(root, filename)
            if (root / filename).is_symlink() or path.stat().st_size > 65536:
                raise AutomationPilotDenied('Remote review source file is unqualified')
            if _git(root, 'hash-object', filename) != expected_blob:
                raise AutomationPilotDenied('Remote review source blob is unqualified')
        manifest = json.loads(_source_file(root, REMOTE_MANIFEST).read_text(encoding='utf-8'))
        # Compare canonical wire shape, not Python equality (True == 1).
        if json.dumps(manifest, sort_keys=True) != json.dumps(_EXPECTED_MANIFEST, sort_keys=True):
            raise AutomationPilotDenied('Remote review operation is unqualified')
    except (OSError, TypeError, ValueError) as exc:
        raise AutomationPilotDenied('Remote preflight source review is unavailable') from exc
    material = {
        'schema': 'kaori.automation.remote_source_review.v1',
        'revision': REMOTE_CANDIDATE_SHA,
        'blobs': _EXPECTED_BLOBS,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return RemoteSourceReview(REMOTE_CANDIDATE_SHA, digest)
