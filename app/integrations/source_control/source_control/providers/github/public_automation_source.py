"""Pinned, bounded GitHub source-read contract for the first public Kubespray profile.

GitHub is authoritative for Git objects. This provider-specific transport reads
only a fixed public repository at one immutable candidate commit. It neither
accepts arbitrary URLs nor authorizes execution/host targets. Registered source
evidence is not operational validation or provider readiness.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

REPOSITORY = 'OXY7O/kaori-operations'
SOURCE_CANDIDATE_SHA = '831ab7c114b1c1ba777c08ab79c91415ad8d465d'
PROFILE_KEY = 'kubernetes_lifecycle'
KUBESPRAY_RELEASE = 'v2.32.0'
KUBESPRAY_COMMIT = '9751ea6f63244e433a7a6263d9ecf381e57bb8e9'
ANSIBLE_CORE_VERSION = '2.19.3'
ANSIBLE_RUNNER_VERSION = '2.4.3'
_REQUIRED_BLOBS = {
    'automation/operations.json': '4be91c6b9b0537ffe965ebff86eb76bfd576e333',
    'ansible/playbooks/linux_host_facts.yml': 'ad8ffb5d72f6ed512c30ce5cfca29b4ffb0b4e9e',
    'ansible/inventory/examples/localhost.ini': '13b316e457c29affe8cec3ba1cbfaada30ac0680',
    'execution-environments/requirements.txt': '78ac0ec89316f0c02799afbdedddab88e0ef27b6',
    'kubernetes/self-managed/profiles/kubespray-v2.32.0-pilot.json': 'b8f50d37f61392b11ff22cc7bfd3586796dc4c92',
}
_SHA = re.compile(r'[0-9a-f]{40}\Z')
_ORIGIN = 'https://api.github.com'
_MAX_BYTES = 262_144


class AutomationSourceRejected(ValueError):
    """Public source has not established reviewed immutable provenance."""


@dataclass(frozen=True, slots=True)
class PublicSourceEvidence:
    repository: str
    revision: str
    tree_sha: str
    profile_key: str
    checked_files: int
    observed_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            'repository': self.repository,
            'revision': self.revision,
            'tree_sha': self.tree_sha,
            'profile_key': self.profile_key,
            'checked_files': self.checked_files,
            'observed_at': self.observed_at,
            'status': 'source_checked',
            'operation_authorized': False,
        }


def _get_object(path: str, *, session: requests.Session) -> dict[str, Any]:
    response = None
    try:
        response = session.get(
            f'{_ORIGIN}{path}',
            headers={
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
            },
            timeout=(3, 10),
            verify=True,
            allow_redirects=False,
            stream=True,
        )
        if response.status_code != 200:
            raise AutomationSourceRejected('Public Git source request was unavailable or rejected.')
        data = bytearray()
        for chunk in response.iter_content(chunk_size=16_384):
            data.extend(chunk)
            if len(data) > _MAX_BYTES:
                raise AutomationSourceRejected('Git source metadata exceeds allowed size.')
        payload = json.loads(bytes(data))
        if not isinstance(payload, dict):
            raise AutomationSourceRejected('Git source metadata was not a JSON object.')
        return payload
    except (requests.RequestException, UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, AutomationSourceRejected):
            raise
        raise AutomationSourceRejected('Git source could not be verified with trusted TLS.') from exc
    finally:
        if response is not None:
            response.close()


def verify_public_kubespray_source(
    repository: str,
    revision: str,
    *,
    session_factory: Callable[[], requests.Session] = requests.Session,
) -> PublicSourceEvidence:
    """Verify real immutable Git object names/blobs, not only filenames.

    The one approved **candidate** profile is non-executable and non-production.
    Future repository or version support requires independent source-adapter
    admission; arbitrary repository URLs are never accepted as network input.
    """
    if repository != REPOSITORY or revision != SOURCE_CANDIDATE_SHA or not _SHA.fullmatch(revision):
        raise AutomationSourceRejected('The source is outside the reviewed public pilot profile.')
    session = session_factory()
    session.trust_env = False
    try:
        commit = _get_object(f'/repos/{REPOSITORY}/git/commits/{revision}', session=session)
        tree = commit.get('tree')
        if commit.get('sha') != revision or not isinstance(tree, dict):
            raise AutomationSourceRejected('Git commit identity could not be verified.')
        tree_sha = tree.get('sha')
        if not isinstance(tree_sha, str) or not _SHA.fullmatch(tree_sha):
            raise AutomationSourceRejected('Git commit does not contain a trusted tree SHA.')
        snapshot = _get_object(f'/repos/{REPOSITORY}/git/trees/{tree_sha}?recursive=1', session=session)
        if snapshot.get('sha') != tree_sha or snapshot.get('truncated') is not False:
            raise AutomationSourceRejected('Git tree is incomplete or does not match the commit.')
        entries = snapshot.get('tree')
        if not isinstance(entries, list) or len(entries) > 8192:
            raise AutomationSourceRejected('Git file tree is missing or out of bounds.')
        blobs: dict[str, str] = {}
        for item in entries:
            if not isinstance(item, dict):
                raise AutomationSourceRejected('Git source tree contains invalid entries.')
            name = item.get('path')
            if name in _REQUIRED_BLOBS:
                if name in blobs or item.get('type') != 'blob' or item.get('mode') not in {'100644', '100755'}:
                    raise AutomationSourceRejected('Required Git source file type is unsafe.')
                blobs[name] = str(item.get('sha') or '')
        if blobs != _REQUIRED_BLOBS:
            raise AutomationSourceRejected(
                'Required Kubespray manifest, playbook or version policy differs from reviewed Git blobs.'
            )
        return PublicSourceEvidence(
            repository=REPOSITORY,
            revision=revision,
            tree_sha=tree_sha,
            profile_key=PROFILE_KEY,
            checked_files=len(_REQUIRED_BLOBS),
            observed_at=datetime.now(UTC).isoformat(),
        )
    finally:
        session.close()
