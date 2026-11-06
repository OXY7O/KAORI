"""Regression contract for the bounded branch-ruleset evidence handover (#4216).

This test validates documentation assertions, not effective GitHub settings.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/engineering/KAORI_BRANCH_RULESETS_EVIDENCE.md"


def test_ruleset_handover_does_not_claim_unverified_controls() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    assert "PARTIALLY VERIFIED, NOT ACCEPTED" in text
    assert "26596521" in text
    assert "refs/heads/main" in text
    assert "refs/heads/kaori/staging" in text
    assert "deletion" in text and "non_fast_forward" in text

    unverified = (
        "Required PR review / resolved conversations",
        "Exact required check contexts",
        "Direct-push prevention / merge method policy",
        "Repository Actions permissions / runner groups / environments",
        "Organization 2FA / app permissions / emergency access",
        "Website and Docs repository protections",
    )
    for control in unverified:
        rows = [line for line in text.splitlines() if line.startswith(f"| {control} |")]
        assert len(rows) == 1, control
        assert "| NOT VERIFIED |" in rows[0], control


def test_ruleset_handover_preserves_admission_and_security_boundaries() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    for required in (
        "external-fork negative test",
        "kaori/review/staging-uat",
        "NOT VERIFIED",
        "NO-GO",
        "Full Admission",
        "GitHub Project Status",
        "privileged self-hosted runners",
    ):
        assert required in text
