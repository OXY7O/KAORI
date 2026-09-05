from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"
HERO = TEMPLATES / "components" / "page_hero.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_page_hero_exposes_one_canonical_profile_renderer() -> None:
    source = _read(HERO)

    assert "macro render(" in source
    assert "hero_profile" in source
    assert "hero_state" in source
    assert "operational-dashboard" in source
    assert "normal" in source
    assert "blocked" in source
    assert "degraded" in source


def test_authenticated_hero_consumers_do_not_assemble_shell_geometry_directly() -> None:
    offenders: list[str] = []

    for path in TEMPLATES.rglob("*.html"):
        if path == HERO:
            continue
        source = _read(path)
        if "page_hero.shell_classes()" in source:
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, "Direct Hero shell composition remains in: " + ", ".join(offenders)


def test_operational_dashboard_heroes_use_one_profile_and_semantic_grammar() -> None:
    kubernetes = _read(TEMPLATES / "kubernetes" / "dashboard" / "partials" / "_hero.html")
    object_storage = _read(
        TEMPLATES / "storage" / "object_storage" / "dashboard" / "partials" / "_hero.html"
    )

    for source in (kubernetes, object_storage):
        assert "page_hero.render(" in source
        assert "hero_profile='operational-dashboard'" in source
        assert "hero_state=" in source
        assert "Data Authority" in source
        assert "Committed Snapshots" in source
        assert "Active Scope" in source


def test_object_storage_analytics_normal_branch_has_three_factual_metadata_slots() -> None:
    source = _read(
        TEMPLATES / "storage" / "object_storage" / "analytics" / "partials" / "_hero.html"
    )

    assert "page_hero.render(" in source
    assert "Inventory Not Collected" in source
    assert "if inventory_observed_at" not in source.split("dependency_blocker", 1)[-1]
