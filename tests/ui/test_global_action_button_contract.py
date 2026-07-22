from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"


def _templates():
    return list(TEMPLATES.rglob("*.html"))


def test_secret_reveal_save_readiness_uses_global_primary_contract():
    source = (TEMPLATES / "settings/secret_reveal/_cluster_workspace.html").read_text()
    assert "Save Readiness" in source
    assert 'data-lucide="save"' in source
    assert "bg-kaori-primary" in source
    assert "hover:bg-kaori-primary-hover" in source
    assert "active:bg-kaori-primary-dark" in source
    assert "cursor-pointer" in source
    assert "disabled:cursor-not-allowed" in source
    assert "Save readiness" not in source


def test_no_legacy_blue_primary_button_remains():
    violations = []
    for path in _templates():
        source = path.read_text()
        for match in re.finditer(r"<button\\b[^>]*>", source, flags=re.I | re.S):
            tag = match.group(0)
            if "bg-blue-" in tag:
                violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Legacy blue button styling remains in: {sorted(set(violations))}"


def test_colored_mutation_buttons_expose_pointer_and_disabled_cursor():
    violations = []
    for path in _templates():
        source = path.read_text()
        for match in re.finditer(r"<button\\b(?P<attrs>[^>]*)>", source, flags=re.I | re.S):
            attrs = match.group("attrs")
            class_match = re.search(r'class=["\\\'](?P<classes>.*?)["\\\']', attrs, flags=re.S)
            if not class_match:
                continue
            classes = class_match.group("classes")
            is_mutation = (
                re.search(r'type=["\\\']submit["\\\']', attrs, flags=re.I)
                or "bg-kaori-primary" in classes
                or "bg-status-critical" in classes
                or "bg-red-" in classes
                or "border-status-critical" in classes
            )
            if not is_mutation:
                continue
            if "cursor-pointer" not in classes or "disabled:cursor-not-allowed" not in classes:
                line = source[: match.start()].count("\\n") + 1
                violations.append(f"{path.relative_to(ROOT)}:{line}")
    assert not violations, "Mutation button cursor contract violations:\\n" + "\\n".join(violations)


def test_button_standard_is_linked_from_design_index():
    index = (ROOT / "docs/design/README.md").read_text()
    standard = (ROOT / "docs/design/components/BUTTON.md").read_text()
    assert "components/BUTTON.md" in index
    assert "Primary Bright Violet" in standard
    assert "Title Case" in standard
    assert "cursor-pointer" in standard
