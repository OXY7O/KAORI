from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / 'docs/security/PUBLIC_SOURCE_RIGHTS_AUDIT.md'
LICENSE = ROOT / 'LICENSE'


def test_publication_audit_requires_history_artifacts_and_rights_evidence() -> None:
    content = AUDIT.read_text(encoding='utf-8')
    assert '**Decision: NO-GO' in content
    for surface in (
        'Tracked HEAD tree',
        'Full Git history',
        'GitHub releases and assets',
        'Workflow logs and artifacts',
        'Third-party rights',
        'Organization ownership',
        'Website and Docs',
        'Secret-scanning effectiveness',
    ):
        assert f'| {surface} |' in content
    assert content.count('| NOT VERIFIED |') == 8
    assert 'tracked-tree scan alone cannot establish' in content
    assert 'per-repository GO decision' in content


def test_publication_audit_does_not_authorize_license_cutover_or_public_findings() -> None:
    content = AUDIT.read_text(encoding='utf-8')
    assert 'approved private audit location' in content
    assert 'separately authorized rotation/revocation' in content
    assert 'Do not change `LICENSE`' in content
    assert '#4213' in content
    assert '#4215' in content
    assert LICENSE.is_file()


def test_public_metadata_snapshot_never_replaces_rights_signoff() -> None:
    content = AUDIT.read_text(encoding='utf-8')
    assert 'Verified public repository metadata' in content
    for repo in ('OXY7O/KAORI', 'OXY7O/kaori-website', 'OXY7O/kaori-docs'):
        assert repo in content
    assert content.count('KAORI INTERNAL USE LICENSE') == 2
    assert 'Root `LICENSE` absent' in content
    assert 'not equivalent to open-source licensing' in content
    assert 'No current license file was changed' in content
    assert content.count('| NOT VERIFIED |') == 8
    assert '**Decision: NO-GO' in content


def test_release_and_workflow_snapshot_is_partial_not_exposure_clearance() -> None:
    content = AUDIT.read_text(encoding='utf-8')
    assert 'Public release and workflow metadata snapshot — 2026-11-08' in content
    for repo in ('OXY7O/KAORI', 'OXY7O/kaori-website', 'OXY7O/kaori-docs'):
        assert repo in content
    assert '3,583' in content and '251' in content and '222' in content
    assert '0 attached Release assets' in content
    assert 'not** mean no registry OCI images' in content
    assert 'NOT VERIFIED**, not zero' in content
    assert 'not** a completed pagination' in content
    assert '**Decision: NO-GO' in content
    assert content.count('| NOT VERIFIED |') == 8
