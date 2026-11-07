#!/usr/bin/env python3
"""Sanitized, read-only GitHub Release asset metadata inventory for #4212.

Never downloads assets or reports names, URLs, authors, descriptions or content.
Retained metadata is not historical exposure, secret, license or rights clearance.
"""
import argparse
import json
import re
import subprocess

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 1000
MAX_ASSETS = 100000


def inventory(repository, runner=subprocess.run):
    if (not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(p in (".", "..") for p in repository.split("/"))):
        raise ValueError("invalid owner/repository")
    command = ["gh", "api", "--paginate", "--slurp",
               f"repos/{repository}/releases?per_page=100"]
    result = {"repository": repository, "assessment": "INCOMPLETE",
              "release_metadata_access": "FAILED_OR_INCOMPLETE",
              "release_count": None, "asset_count": None,
              "draft_count": None, "prerelease_count": None,
              "limitations": "No historical, asset-content, secret, attribution or rights clearance"}
    try:
        response = runner(command, capture_output=True, text=True,
                          check=False, timeout=30)
        if response.returncode:
            raise ValueError("API failed")
        if not isinstance(response.stdout, str) or len(response.stdout.encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise ValueError('response exceeds inventory budget')
        def reject_duplicate_keys(pairs):
            record = {}
            for key, value in pairs:
                if key in record:
                    raise ValueError("ambiguous JSON metadata")
                record[key] = value
            return record

        pages = json.loads(response.stdout, object_pairs_hook=reject_duplicate_keys)
        if not isinstance(pages, list) or not pages or len(pages) > MAX_PAGES:
            raise ValueError("invalid pagination")
        releases = []
        for page in pages:
            if not isinstance(page, list):
                raise ValueError("invalid page")
            releases.extend(page)
        ids, asset_ids = set(), set()
        asset_count = drafts = prereleases = 0
        for release in releases:
            if not isinstance(release, dict):
                raise ValueError("invalid release")
            rid = release.get("id")
            if type(rid) is not int or rid <= 0 or rid in ids:
                raise ValueError("invalid release ID")
            ids.add(rid)
            if type(release.get("draft")) is not bool or type(release.get("prerelease")) is not bool:
                raise ValueError("invalid release flags")
            drafts += release["draft"]
            prereleases += release["prerelease"]
            assets = release.get("assets")
            if not isinstance(assets, list):
                raise ValueError("invalid assets")
            for asset in assets:
                if not isinstance(asset, dict):
                    raise ValueError("invalid asset")
                aid = asset.get("id")
                if type(aid) is not int or aid <= 0 or aid in asset_ids:
                    raise ValueError("invalid asset ID")
                asset_ids.add(aid)
                asset_count += 1
                if asset_count > MAX_ASSETS:
                    raise ValueError('asset inventory exceeds budget')
        # GitHub release listings are retention- and permission-dependent; no
        # historical completeness can be inferred from successful pagination.
        result.update(release_metadata_access="READ", release_count=len(releases),
                      asset_count=asset_count, draft_count=drafts,
                      prerelease_count=prereleases,
                      limitations="Accessible release/asset metadata only; deleted releases, asset bytes, workflow logs, secrets and rights not reviewed")
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repositories", nargs="+")
    args = parser.parse_args()
    print(json.dumps([inventory(repo) for repo in args.repositories], indent=2))


if __name__ == "__main__":
    main()
