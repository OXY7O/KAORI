from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "docs/security/GITHUB_NATIVE_SECURITY_BASELINE.md"
SECURITY = ROOT / "SECURITY.md"


def test_native_security_register_never_implies_unverified_enablement() -> None:
    content = BASELINE.read_text(encoding="utf-8")
    assert "**Status: PREPARED / NOT VERIFIED.**" in content
    for control in (
        "Dependency Graph",
        "Dependabot alerts",
        "Dependabot security updates",
        "Dependabot version updates",
        "Secret scanning",
        "Push protection",
        "CodeQL / code scanning",
        "Dependency review",
        "Private vulnerability reporting",
        "Security advisory workflow",
    ):
        assert f"| {control} | NOT VERIFIED |" in content
    assert "NO-GO" in content
    assert "#4212" in content
    assert "#4216" in content
    assert "#4220" in content


def test_security_baseline_preserves_private_reporting_and_fork_boundary() -> None:
    baseline = BASELINE.read_text(encoding="utf-8")
    policy = SECURITY.read_text(encoding="utf-8")
    assert "Do **not** open a public Issue" in policy
    assert "Route suspected vulnerabilities privately" in baseline
    assert "dependabot/*" in baseline
    assert "pull_request_target" in baseline
    assert "workflow_run" in baseline
    assert "human acceptance" in baseline
