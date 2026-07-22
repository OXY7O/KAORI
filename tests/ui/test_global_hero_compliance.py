from pathlib import Path
import re

TEMPLATES = Path("app/templates")
EXCLUDED = {
    "app/templates/auth/partials/_brand_panel.html",
    "app/templates/errors/403.html",
    "app/templates/components/navigation/sidebar.html",
}


def _authenticated_hero_templates():
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "<h1" not in text:
            continue
        if path.as_posix() in EXCLUDED:
            continue
        yield path, text


def test_no_legacy_blue_gradient_hero_remains():
    failures = []
    for path, text in _authenticated_hero_templates():
        if "bg-gradient-to-r from-blue-700 via-blue-600 to-cyan-500" in text:
            failures.append(path.as_posix())
    assert not failures, "Legacy blue gradient hero remains: " + ", ".join(failures)


def test_shared_hero_typography_is_canonical():
    text = Path("app/templates/components/page_hero.html").read_text(encoding="utf-8")
    assert "text-[30px]" in text
    assert "lg:text-[32px]" in text
    assert "text-[15px]" in text
    assert "leading-6" in text
    assert "text-[10px]" in text
    assert "tracking-[0.14em]" in text


def test_shared_hero_geometry_is_canonical():
    text = Path("app/templates/components/page_hero.html").read_text(encoding="utf-8")
    assert "min-h-[15.5rem]" in text
    assert "lg:min-h-[17.5rem]" in text
    assert "xl:col-span-7" in text
    assert "xl:col-span-5" in text


def test_static_metadata_rows_do_not_render_more_than_three_labels():
    failures = []
    for path, text in _authenticated_hero_templates():
        for block in re.findall(r'<div class="\{\{ page_hero\.metadata_row_classes\(\) \}\}">(.*?)</div>', text, re.S):
            count = block.count("page_hero.meta_label(")
            if count > 3:
                failures.append(f"{path.as_posix()} ({count})")
    assert not failures, "Hero metadata exceeds three labels: " + ", ".join(failures)
