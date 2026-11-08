#!/usr/bin/env python3
"""Read-only, sanitized Git history coverage preflight for publication audit #4212.

This is an inventory of local evidence completeness, NOT a secrets/IP scan or clearance.
Never prints commit messages, file paths, remote URLs, author identities or secrets.
"""

import json
import subprocess


def inventory(runner=subprocess.run):
    commands = (
        ['git', 'rev-parse', '--is-shallow-repository'],
        ['git', 'rev-list', '--all', '--count'],
        ['git', 'for-each-ref', '--format=%(refname)', 'refs/heads', 'refs/tags'],
    )
    try:
        results = []
        for command in commands:
            result = runner(command, capture_output=True, text=True, check=False, timeout=30)
            if result.returncode:
                raise ValueError('git command failed')
            results.append(result.stdout.strip())
        shallow, count_text, refs_text = results
        if shallow not in ('true', 'false') or not count_text.isdecimal():
            raise ValueError('invalid git metadata')
        count = int(count_text)
        refs = refs_text.splitlines() if refs_text else []
        if count < 1 or not refs or len(refs) != len(set(refs)):
            raise ValueError('incomplete refs')
        if any(
            not (ref.startswith('refs/heads/') or ref.startswith('refs/tags/')) or ref in ('refs/heads/', 'refs/tags/')
            for ref in refs
        ):
            raise ValueError('invalid refs')
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {
            'assessment': 'INCOMPLETE',
            'history_metadata_access': 'FAILED_OR_INCOMPLETE',
            'commit_count': None,
            'local_ref_count': None,
            'shallow': None,
            'limitations': 'No historical content, secret or rights clearance',
        }
    return {
        'assessment': 'INCOMPLETE',
        'history_metadata_access': 'READ',
        'commit_count': count,
        'local_ref_count': len(refs),
        'shallow': shallow == 'true',
        'limitations': 'Local refs only; unreachable commits, deleted refs, remote history, secrets and IP not audited',
    }


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
