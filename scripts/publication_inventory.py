#!/usr/bin/env python3
"""Read-only, metadata-only local Git publication inventory (#4212).

This does not scan for secrets or establish publication/rights clearance.
"""
import argparse
import json
import subprocess
from pathlib import Path


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=True)
    return result.stdout


def inventory(repo):
    repo = Path(repo).resolve()
    if git(repo, 'rev-parse', '--is-inside-work-tree').strip() != b'true':
        raise ValueError('not a git worktree')
    commits = int(git(repo, 'rev-list', '--all', '--count').strip())
    refs = git(repo, 'for-each-ref', '--format=%(refname)', 'refs/heads', 'refs/tags').splitlines()
    tracked = git(repo, 'ls-files', '-z').split(b'\0')
    tracked_count = sum(bool(name) for name in tracked)
    history_objects = git(repo, 'rev-list', '--objects', '--all').splitlines()
    return {'repository': repo.name, 'history_commit_count': commits,
            'local_branch_and_tag_ref_count': len(refs),
            'tracked_head_file_count': tracked_count,
            'reachable_history_object_count': len(history_objects),
            'assessment': 'INCOMPLETE',
            'limitations': 'Local refs only; no remote release assets, Actions logs/artifacts, secret scanning, ownership or license clearance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repositories', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps([inventory(repo) for repo in args.repositories], indent=2))


if __name__ == '__main__':
    main()
