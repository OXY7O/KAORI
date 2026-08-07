from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_dark_mode_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_dark_mode_standard.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "KAORI dark mode standard passed" in result.stdout


def test_dark_mode_document_is_registered_as_authoritative() -> None:
    readme = (ROOT / "docs" / "design" / "README.md").read_text(encoding="utf-8")
    entrypoint = (ROOT / "docs" / "design" / "DESIGN_SYSTEM.md").read_text(encoding="utf-8")
    standard = (ROOT / "docs" / "design" / "components" / "DARK_MODE.md").read_text(encoding="utf-8")

    assert "neutral-first dark surfaces" in readme
    assert "locked neutral-first dark surface" in entrypoint
    assert "80% neutral operational surfaces" in standard
    assert "The only approved exception is the canonical dark Hero gradient" in standard
    assert "Deep Violet contextual surfaces" in standard
    assert "components/related_page_card.html" in standard


def test_obsolete_raw_slate_topbar_is_removed() -> None:
    obsolete = ROOT / "app" / "templates" / "components" / "navigation" / "topbar.html"
    assert not obsolete.exists()


def test_related_page_card_uses_the_global_deep_violet_context_surface() -> None:
    component = (ROOT / "app" / "templates" / "components" / "related_page_card.html").read_text(encoding="utf-8")
    standard = (ROOT / "docs" / "design" / "components" / "RELATED_PAGE_CARD.md").read_text(encoding="utf-8")

    assert "kaori-brand-domain-panel" in component
    assert "dark:bg-surface-card" not in component
    assert "#2F1A4F" in standard
    assert "do not add page-local `dark:bg-*` overrides" in standard
