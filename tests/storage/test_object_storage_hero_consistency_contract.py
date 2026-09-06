from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_object_storage_inventory_setup_copy_is_concise() -> None:
    source = (
        ROOT
        / "app"
        / "templates"
        / "storage"
        / "object_storage"
        / "inventory"
        / "components"
        / "_onboarding_banner.html"
    ).read_text(encoding="utf-8")

    assert "Register a Storage integration before KAORI collects object-storage snapshots." in source
    assert "before KAORI can collect and present committed object-storage systems" not in source


def test_object_storage_analytics_uses_shared_three_slot_metadata_renderer() -> None:
    source = (
        ROOT
        / "app"
        / "templates"
        / "storage"
        / "object_storage"
        / "analytics"
        / "partials"
        / "_hero.html"
    ).read_text(encoding="utf-8")

    assert "page_hero.analytics_metadata(" in source
    assert "page_hero.metadata_row_classes()" not in source
    assert "Committed Snapshot Boundary" in source
