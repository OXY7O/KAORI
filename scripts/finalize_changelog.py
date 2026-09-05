from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

SEMVER_RE = re.compile(r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
UNRELEASED = '## [Unreleased]'


def finalize_changelog(text: str, version: str, release_date: str) -> str:
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f'invalid stable SemVer: {version}')
    try:
        date.fromisoformat(release_date)
    except ValueError as exc:
        raise ValueError(f'invalid ISO release date: {release_date}') from exc

    version_heading = f'## [{version}] - {release_date}'
    if version_heading in text or f'## [{version}]' in text:
        raise ValueError(f'changelog already contains version {version}')

    marker = f'{UNRELEASED}\n'
    if marker not in text:
        raise ValueError('CHANGELOG.md is missing [Unreleased] section')

    prefix, remainder = text.split(marker, 1)
    if not remainder.strip():
        raise ValueError('[Unreleased] section is empty')

    return f'{prefix}{UNRELEASED}\n\n{version_heading}\n{remainder.lstrip()}'


def main() -> int:
    parser = argparse.ArgumentParser(description='Finalize KAORI changelog for a stable SemVer release.')
    parser.add_argument('version', help='Stable SemVer without v prefix, for example 0.1.1')
    parser.add_argument('--date', dest='release_date', default=date.today().isoformat(), help='ISO date, default: today')
    parser.add_argument('--path', type=Path, default=Path('CHANGELOG.md'))
    parser.add_argument('--check', action='store_true', help='Validate transformation without writing the file')
    args = parser.parse_args()

    try:
        current = args.path.read_text(encoding='utf-8')
        updated = finalize_changelog(current, args.version, args.release_date)
    except (OSError, ValueError) as exc:
        print('FAIL — Release Changelog')
        print(f'  reason  : {exc}')
        return 1

    print('== KAORI Release · Changelog ==')
    print(f'  version : v{args.version}')
    print(f'  date    : {args.release_date}')
    print(f'  path    : {args.path}')
    if args.check:
        print('PASS — changelog release transformation is valid')
        return 0

    args.path.write_text(updated, encoding='utf-8')
    print('PASS — changelog finalized; [Unreleased] retained for the next cycle')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
