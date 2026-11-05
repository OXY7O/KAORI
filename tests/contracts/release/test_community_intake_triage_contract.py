from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRIAGE = ROOT / "docs/engineering/COMMUNITY_INTAKE_TRIAGE.md"


def test_community_intake_is_explicitly_prelaunch_and_issue_governed() -> None:
    content = TRIAGE.read_text(encoding="utf-8")
    assert "pre-launch / maintainer preparation" in content
    assert "does not assert that GitHub Discussions" in content
    assert "GitHub Project" in content
    assert "create one bounded Issue" in content
    assert "maintainer-owned issue-linked branch" in content
    assert "normal trusted gates" in content


def test_community_intake_preserves_private_security_and_acceptance() -> None:
    content = TRIAGE.read_text(encoding="utf-8")
    assert "[SECURITY.md](../../SECURITY.md)" in content
    assert "Do not request details publicly" in content
    assert "actual negative-test evidence" in content
    assert "human acceptance" in content
    assert "OXY7O/.github#2" in content


def test_public_readme_does_not_advertise_unapproved_community_launch() -> None:
    """Pre-launch intake guidance must not imply live public support channels."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[\u0053ECURITY.md](SECURITY.md)" in readme
    assert "internal-use proprietary project" in readme
    assert "github.com/OXY7O/KAORI/discussions" not in readme.lower()
    assert "discussions are enabled" not in readme.lower()
    assert "open-source license" not in readme.lower()
