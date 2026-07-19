from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"

CONTROL_RE = re.compile(
    r"<(?P<tag>a|button|span)\b(?P<attrs>[^>]*)>"
    r"(?P<body>(?:(?!</(?P=tag)>).)*?\b(?:Previous|Next)\b(?:(?!</(?P=tag)>).)*?)"
    r"</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)


def _pagination_controls():
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for match in CONTROL_RE.finditer(text):
            body = re.sub(r"<[^>]+>", " ", match.group("body"))
            body = re.sub(r"{{.*?}}|{%.*?%}", " ", body, flags=re.DOTALL)
            label = " ".join(body.split()).lower()
            if label in {"previous", "next"}:
                yield path, text, match.group(0), label


def test_shared_pagination_component_exists():
    component = (TEMPLATES / "components" / "pagination.html").read_text(encoding="utf-8")
    assert "macro navigation_classes" in component
    assert "rounded-md" in component
    assert "cursor-pointer" in component
    assert "cursor-not-allowed" in component
    assert "hover:bg-kaori-soft" in component


def test_all_previous_next_controls_use_shared_component():
    controls = list(_pagination_controls())
    assert controls, "No pagination controls were discovered."
    failures = []
    for path, text, markup, label in controls:
        if 'components/pagination.html' not in text or "pagination_ui.navigation_classes" not in markup:
            failures.append(f"{path.relative_to(ROOT)}: {label}")
    assert not failures, "Local pagination styles remain:\n" + "\n".join(failures)


def test_previous_next_icons_are_present():
    failures = []
    for path, _, markup, label in _pagination_controls():
        icon = "chevron-left" if label == "previous" else "chevron-right"
        if icon not in markup:
            failures.append(f"{path.relative_to(ROOT)}: {label}")
    assert not failures, "Pagination icons are missing:\n" + "\n".join(failures)


def test_pagination_document_requires_shared_component():
    doc = (ROOT / "docs" / "design" / "components" / "PAGINATION.md").read_text(encoding="utf-8")
    assert "Shared component contract" in doc
    assert "must not create provider- or module-specific visual classes" in doc
    assert "Previous and Next are navigation controls" in doc
