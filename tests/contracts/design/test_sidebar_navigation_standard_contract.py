from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_sidebar_navigation_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_sidebar_navigation_standard.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "KAORI sidebar navigation standard passed" in result.stdout


def test_sidebar_standard_is_registered_as_authoritative_design_document() -> None:
    readme = (ROOT / "docs" / "design" / "README.md").read_text(encoding="utf-8")
    design_system = (ROOT / "docs" / "design" / "DESIGN_SYSTEM.md").read_text(encoding="utf-8")
    standard = (ROOT / "docs" / "design" / "components" / "SIDEBAR_NAVIGATION.md").read_text(encoding="utf-8")

    assert "locked application-shell navigation contract" in readme
    assert "locked v1.1 sidebar hierarchy" in design_system
    assert "The earlier 12/11 px markdown baseline" in standard
    assert "15/13 px visual-guide draft" in standard
