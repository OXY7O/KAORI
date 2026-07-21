from __future__ import annotations

import re
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "app" / "templates"
TITLE_PATTERN = re.compile(
    r"{%\s*set\s+empty_state_title\s*=\s*(['\"])(?P<value>.*?)\1\s*%}"
)
ACTION_PATTERN = re.compile(
    r"{%\s*set\s+empty_state_(?:secondary_)?action_label\s*=\s*(['\"])(?P<value>.*?)\1"
)
LOWERCASE_CONNECTORS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}


def _literal_empty_state_values(pattern: re.Pattern[str]):
    for template in TEMPLATE_ROOT.rglob("*.html"):
        content = template.read_text(encoding="utf-8")
        for match in pattern.finditer(content):
            yield template, match.group("value")


def test_empty_state_titles_use_kaori_title_case() -> None:
    violations: list[str] = []
    for template, value in _literal_empty_state_values(TITLE_PATTERN):
        words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", value)
        for index, word in enumerate(words):
            if index and word.lower() in LOWERCASE_CONNECTORS:
                continue
            if word[0].islower():
                violations.append(f"{template.relative_to(TEMPLATE_ROOT)}: {value}")
                break
    assert not violations, "Empty-state titles must use KAORI Title Case:\n" + "\n".join(violations)


def test_empty_state_action_labels_have_at_most_two_words() -> None:
    violations = [
        f"{template.relative_to(TEMPLATE_ROOT)}: {value}"
        for template, value in _literal_empty_state_values(ACTION_PATTERN)
        if len(value.split()) > 2
    ]
    assert not violations, "Empty-state action labels must contain at most two words:\n" + "\n".join(violations)


def test_shared_empty_state_supports_kaori_contract() -> None:
    component = (TEMPLATE_ROOT / "components" / "states" / "_empty_state.html").read_text(encoding="utf-8")
    required_contract = (
        "empty_state_label",
        "empty_state_action_url",
        "empty_state_secondary_action_url",
        "empty_state_permission",
        "empty_state_show_admin_required",
        "data-kaori-empty-state",
    )
    missing = [item for item in required_contract if item not in component]
    assert not missing, f"Shared empty-state component is missing: {', '.join(missing)}"
