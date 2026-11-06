from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "docs/security/PUBLIC_SOURCE_RIGHTS_AUDIT.md"
LICENSE = ROOT / "LICENSE"


def test_publication_audit_requires_history_artifacts_and_rights_evidence() -> None:
    content = AUDIT.read_text(encoding="utf-8")
    assert "**Decision: NO-GO" in content
    for surface in (
        "Tracked HEAD tree",
        "Full Git history",
        "GitHub releases and assets",
        "Workflow logs and artifacts",
        "Third-party rights",
        "Organization ownership",
        "Website and Docs",
        "Secret-scanning effectiveness",
    ):
        assert f"| {surface} |" in content
    assert content.count("| NOT VERIFIED |") == 8
    assert "tracked-tree scan alone cannot establish" in content
    assert "per-repository GO decision" in content


def test_publication_audit_does_not_authorize_license_cutover_or_public_findings() -> None:
    content = AUDIT.read_text(encoding="utf-8")
    assert "approved private audit location" in content
    assert "separately authorized rotation/revocation" in content
    assert "Do not change `LICENSE`" in content
    assert "#4213" in content
    assert "#4215" in content
    assert LICENSE.is_file()
