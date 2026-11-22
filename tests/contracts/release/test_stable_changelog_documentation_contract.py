from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_stable_changelog_is_documented_only_after_actual_publication() -> None:
    governance = (ROOT / 'docs/deployment/RELEASE_GOVERNANCE.md').read_text(encoding='utf-8')
    lifecycle = (ROOT / 'docs/releases/README.md').read_text(encoding='utf-8')
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert '## [Unreleased]' in changelog
    assert '**Only after** the stable tag' in governance
    assert 'Keep `CHANGELOG.md` under `[Unreleased]` until stable publication' in governance
    assert '**After actual publication**' in governance
    assert 'Before a release, move approved entries' not in governance
    assert 'After the actual stable tag and GitHub Release exist' in lifecycle
    assert 'source merge is not release authorization' in governance
    assert 'Actual runtime reconciliation is HOLD under #5094' in governance


def test_stable_notes_are_product_first_not_rc_commit_history() -> None:
    notes_template = (ROOT / 'docs/releases/RELEASE_NOTES_TEMPLATE.md').read_text(encoding='utf-8')
    lifecycle = (ROOT / 'docs/releases/README.md').read_text(encoding='utf-8')
    headings = [
        '## Highlights',
        '## Improvements',
        '## Fixes',
        '## Known Limitations',
    ]
    assert all(heading in notes_template for heading in headings)
    assert [notes_template.index(h) for h in headings] == sorted(notes_template.index(h) for h in headings)
    assert 'users can recognize' in notes_template
    assert 'security, compatibility, migration' in notes_template
    assert 'commit or PR titles' in notes_template
    assert 'RC prerelease notes generated from `git log`' in lifecycle
    assert 'must not' in lifecycle
    workflow = (ROOT / '.github/workflows/release-image.yml').read_text(encoding='utf-8')
    events = workflow.split('on:', 1)[1].split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in events
    assert 'push:' not in events
    assert 'Recheck Reviewed Stable Notes Before Publication' in workflow
