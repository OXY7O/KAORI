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
    # Normalize subdirectory invocations to the repository root: git ls-files
    # otherwise counts only the caller's current subdirectory.
    repo = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    # A shallow checkout cannot establish complete publication history.
    shallow = git(repo, 'rev-parse', '--is-shallow-repository').strip() == b'true'
    commits = int(git(repo, 'rev-list', '--all', '--count').strip())
    refs = git(repo, 'for-each-ref', '--format=%(refname)', 'refs/heads', 'refs/tags').splitlines()
    remote_refs = git(repo, 'for-each-ref', '--format=%(refname)', 'refs/remotes').splitlines()
    other_refs = git(repo, 'for-each-ref', '--format=%(refname)', 'refs/notes', 'refs/stash').splitlines()
    tracked = git(repo, 'ls-files', '-z').split(b'\0')
    tracked_count = sum(bool(name) for name in tracked)
    # Omit path names: filenames containing newlines must not inflate object counts.
    history_objects = git(repo, 'rev-list', '--objects', '--no-object-names', '--all').splitlines()
    return {'repository': repo.name, 'history_commit_count': commits,
            'local_branch_and_tag_ref_count': len(refs),
            'remote_tracking_ref_count': len(remote_refs),
            'other_local_ref_count': len(other_refs),
            'shallow_checkout': shallow,
            'tracked_head_file_count': tracked_count,
            'reachable_history_object_count': len(history_objects),
            'assessment': 'INCOMPLETE',
            'limitations': 'Shallow checkout may omit history; only locally fetched refs are counted; no remote release assets, Actions logs/artifacts, secret scanning, ownership or license clearance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repositories', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps([inventory(repo) for repo in args.repositories], indent=2))


if __name__ == '__main__':
    main()
