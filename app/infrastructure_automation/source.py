"""Strict read-only localhost Ansible pilot source qualification (#4799).

This is not an arbitrary-playbook executor or a remote host authorization system.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from flask import current_app

SOURCE_REPOSITORY = 'OXY7O/kaori-operations'
# Accepted pilot-branch merge from kaori-operations #8; not a remote source grant.
SOURCE_SHA = 'aa5ae076e0cd5e6a2cc4d236608cb470012a7ab2'
PLAYBOOK = 'ansible/playbooks/linux_host_facts.yml'
PLAYBOOK_BLOB = 'ad8ffb5d72f6ed512c30ce5cfca29b4ffb0b4e9e'
INVENTORY = 'ansible/inventory/examples/localhost.ini'
INVENTORY_BLOB = '13b316e457c29affe8cec3ba1cbfaada30ac0680'
OPERATION_ID = 'linux.host_facts.v1'
_ALLOWED_ORIGINS = {
    'https://github.com/OXY7O/kaori-operations.git',
    'https://github.com/OXY7O/kaori-operations',
    'git@github.com:OXY7O/kaori-operations.git',
}
_EXPECTED_MANIFEST: dict[str, Any] = {
    'schema_version': 1,
    'operations': {
        OPERATION_ID: {
            'playbook': PLAYBOOK,
            'mode': 'read_only',
            'become': False,
            'allowed_inventory': INVENTORY,
            'allowed_limit': 'localhost',
        }
    },
}


class AutomationPilotDenied(ValueError):
    """Pilot disabled or requested source/operation does not match allowlist."""


def require_local_pilot_enabled() -> None:
    if current_app.config.get('APP_ENV') not in {'development', 'testing'}:
        raise AutomationPilotDenied('Pilot is limited to non-production application environments')
    if os.getenv('KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED', '').strip().lower() != 'true':
        raise AutomationPilotDenied('The local-only Ansible pilot is disabled')


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=8, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AutomationPilotDenied('Unable to verify immutable automation source') from exc
    return result.stdout.strip()


def _source_file(root: Path, relative: str) -> Path:
    try:
        candidate = (root / relative).resolve(strict=True)
    except OSError as exc:
        raise AutomationPilotDenied('Approved automation file is missing') from exc
    if not candidate.is_file() or not candidate.is_relative_to(root):
        raise AutomationPilotDenied('Automation file escapes reviewed source checkout')
    return candidate


def verify_localhost_source(source_path: str, source_sha: str) -> Path:
    require_local_pilot_enabled()
    if not re.fullmatch(r'[a-f0-9]{40}', source_sha) or source_sha != SOURCE_SHA:
        raise AutomationPilotDenied('Requested source revision is not the approved pilot SHA')
    try:
        root = Path(source_path).resolve(strict=True)
    except OSError as exc:
        raise AutomationPilotDenied('Automation source path is unavailable') from exc
    if not root.is_dir() or _git(root, 'rev-parse', '--show-toplevel') != str(root):
        raise AutomationPilotDenied('Automation source is not an exact Git root')
    if _git(root, 'remote', 'get-url', 'origin') not in _ALLOWED_ORIGINS:
        raise AutomationPilotDenied('Git remote is not the approved automation source')
    if _git(root, 'rev-parse', 'HEAD') != source_sha:
        raise AutomationPilotDenied('Git checkout is not the pinned source revision')
    if _git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise AutomationPilotDenied('Git checkout contains uncommitted changes')
    try:
        manifest = json.loads(_source_file(root, 'automation/operations.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise AutomationPilotDenied('Approved operations manifest is invalid') from exc
    if manifest != _EXPECTED_MANIFEST:
        raise AutomationPilotDenied('Unknown operation or inventory in source manifest')
    for filename, expected_blob in ((PLAYBOOK, PLAYBOOK_BLOB), (INVENTORY, INVENTORY_BLOB)):
        _source_file(root, filename)
        if _git(root, 'hash-object', filename) != expected_blob:
            raise AutomationPilotDenied('Approved Ansible file no longer matches its reviewed blob')
    return root


def normalize_facts(events: list[dict[str, Any]]) -> dict[str, str]:
    """Keep only limited OS/kernel fields; never raw Runner stdout or events."""
    keys = (
        'ansible_distribution',
        'ansible_distribution_version',
        'ansible_os_family',
        'ansible_kernel',
        'ansible_architecture',
    )
    for event in events:
        if event.get('event') != 'runner_on_ok':
            continue
        event_data = event.get('event_data') or {}
        if event_data.get('task_action') not in {'ansible.builtin.setup', 'setup'}:
            continue
        facts = (event_data.get('res') or {}).get('ansible_facts') or {}
        if not isinstance(facts, dict):
            continue
        observed = {key: str(facts[key])[:128] for key in keys if isinstance(facts.get(key), (str, int))}
        if 'ansible_distribution' in observed and 'ansible_kernel' in observed:
            return observed
    raise AutomationPilotDenied('Required source-backed Linux OS/kernel facts were not observed')


def verify_read_only_runner_stats(stats: object) -> None:
    """Prove exactly one successful localhost task and no changed remote hosts.

    Ansible may omit hosts from the changed map when the count is zero.
    Empty/missing stats or a missing successful localhost task are not proof.
    """
    if not isinstance(stats, dict):
        raise AutomationPilotDenied('Ansible play recap statistics are unavailable')
    changed = stats.get('changed')
    ok = stats.get('ok')
    if not isinstance(changed, dict) or not isinstance(ok, dict):
        raise AutomationPilotDenied('Ansible play recap lacks changed/ok host evidence')
    if set(ok) != {'localhost'} or type(ok.get('localhost')) is not int or ok['localhost'] < 1:
        raise AutomationPilotDenied('Read-only execution was not limited to successful localhost tasks')
    if any(type(count) is not int or count != 0 for count in changed.values()):
        raise AutomationPilotDenied('Read-only operation reported an infrastructure change')
    if set(changed) - {'localhost'}:
        raise AutomationPilotDenied('Unexpected host appeared in execution change evidence')
    for bucket in ('failures', 'dark', 'unreachable'):
        values = stats.get(bucket, {})
        if not isinstance(values, dict) or any(type(count) is not int or count != 0 for count in values.values()):
            raise AutomationPilotDenied('Read-only execution contains failed or unreachable hosts')
