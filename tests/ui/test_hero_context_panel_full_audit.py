from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"


def _hero_templates() -> list[Path]:
    return [
        path
        for path in TEMPLATES.rglob("*.html")
        if "components/page_hero.html" in path.read_text(encoding="utf-8")
    ]


def _context_panel_templates() -> list[Path]:
    return [
        path
        for path in _hero_templates()
        if "page_hero.aside_classes" in path.read_text(encoding="utf-8")
    ]


def test_all_hero_asides_use_shared_context_panel_geometry() -> None:
    templates = _context_panel_templates()
    assert len(templates) == 31

    failures = []
    for path in templates:
        source = path.read_text(encoding="utf-8")
        if "page_hero.context_panel_classes()" not in source:
            failures.append(str(path.relative_to(ROOT)))

    assert not failures, "Hero panels missing shared geometry: " + ", ".join(failures)


def test_legacy_local_hero_panel_wrapper_is_not_reintroduced() -> None:
    legacy = "min-h-[12rem] flex-col"
    failures = []
    for path in _context_panel_templates():
        source = path.read_text(encoding="utf-8")
        aside_tail = source.split("page_hero.aside_classes", 1)[1]
        if legacy in aside_tail[:1800]:
            failures.append(str(path.relative_to(ROOT)))

    assert not failures, "Legacy Hero wrappers found: " + ", ".join(failures)


def test_reference_implementations_use_shared_context_panel_contract() -> None:
    metric_references = [
        TEMPLATES / "inventory" / "nodes" / "partials" / "_hero.html",
        TEMPLATES / "integrations" / "alertmanager.html",
    ]
    for path in metric_references:
        source = path.read_text(encoding="utf-8")
        assert "page_hero.context_panel_classes()" in source
        assert source.count("page_hero.context_metric(") == 2

    detail = TEMPLATES / "alertmanager" / "instance_detail.html"
    assert "page_hero.context_panel_classes()" in detail.read_text(encoding="utf-8")


def test_standardized_metadata_suffixes_use_title_case() -> None:
    forbidden = (
        "' scope bindings'",
        "' registered connections'",
        "' ready sources'",
        "' active alerts'",
        "' activities recorded'",
        "' nodes tracked'",
        "' namespaces tracked'",
        "' pods tracked'",
        "' services tracked'",
        "' objects tracked'",
        "' actionable'",
    )
    failures = []
    for path in _hero_templates():
        source = path.read_text(encoding="utf-8")
        for fragment in forbidden:
            if fragment in source:
                failures.append(f"{path.relative_to(ROOT)}: {fragment}")

    assert not failures, "Lower-case Hero metadata remains: " + ", ".join(failures)
