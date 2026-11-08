#!/usr/bin/env python3
"""Read-only GitHub release/asset metadata inventory for #4212.

Never outputs release names, asset filenames, URLs, descriptions or contents.
This is not a secret scan, rights review or publication clearance.
"""

import argparse
import json
import re
import subprocess


def inventory(repository, runner=subprocess.run):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('invalid owner/repository')
    command = ['gh', 'api', '--paginate', '--slurp', f'repos/{repository}/releases?per_page=100']
    try:
        result = runner(command, capture_output=True, text=True, check=False)
    except OSError:
        result = None
    if result is None or result.returncode != 0:
        return {
            'repository': repository,
            'assessment': 'INCOMPLETE',
            'release_metadata_access': 'FAILED',
            'release_count': None,
            'asset_count': None,
            'limitations': 'Release metadata unavailable; no exposure or rights clearance',
        }
    try:
        pages = json.loads(result.stdout)
        if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
            raise ValueError('invalid release pagination')
        releases = [release for page in pages for release in page]
        if any(
            not isinstance(release, dict)
            or not isinstance(release.get('id'), int)
            or isinstance(release.get('id'), bool)
            or not isinstance(release.get('assets'), list)
            for release in releases
        ):
            raise ValueError('invalid release metadata')
        ids = [release['id'] for release in releases]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate release IDs')
        for release in releases:
            asset_ids = [asset.get('id') for asset in release['assets'] if isinstance(asset, dict)]
            if (
                len(asset_ids) != len(release['assets'])
                or any(not isinstance(asset_id, int) or isinstance(asset_id, bool) for asset_id in asset_ids)
                or len(asset_ids) != len(set(asset_ids))
            ):
                raise ValueError('invalid or duplicate asset IDs')
    except (ValueError, TypeError):
        return {
            'repository': repository,
            'assessment': 'INCOMPLETE',
            'release_metadata_access': 'INVALID',
            'release_count': None,
            'asset_count': None,
            'limitations': 'Invalid or partial release metadata; no clearance',
        }
    return {
        'repository': repository,
        'assessment': 'INCOMPLETE',
        'release_metadata_access': 'READ',
        'release_count': len(releases),
        'asset_count': sum(len(release['assets']) for release in releases),
        'limitations': 'Metadata counts only; asset contents, workflow artifacts/logs, historical deletion, secrets and rights remain unreviewed',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repositories', nargs='+')
    args = parser.parse_args()
    print(json.dumps([inventory(repo) for repo in args.repositories], indent=2))


if __name__ == '__main__':
    main()
