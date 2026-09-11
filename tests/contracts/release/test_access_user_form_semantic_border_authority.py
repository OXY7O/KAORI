from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'access' / 'users' / 'form.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-border\b'
)
SHARED_BORDER = 'semantic_ui.tone_border_classes('


def test_user_form_uses_shared_semantic_border_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_label.html" as semantic_ui %}' in source
    assert source.count(SHARED_BORDER) == 7
    assert SEMANTIC_BORDER.search(source) is None

    assert "border-b {{ semantic_ui.tone_border_classes('critical') }} bg-status-critical-soft" in source
    assert (
        "rounded-lg border {{ semantic_ui.tone_border_classes('critical') }} bg-surface-card text-status-critical-text"
    ) in source
    assert ("rounded-md border {{ semantic_ui.tone_border_classes('warning') }} bg-status-warning-soft") in source
    assert (
        "semantic_ui.tone_border_classes('normal') if identity_context.provider_enabled "
        "else semantic_ui.tone_border_classes('warning')"
    ) in source
    assert ("rounded-xl border {{ semantic_ui.tone_border_classes('warning') }} bg-status-warning-soft") in source

    # Preserve the actual behavior and semantic state contracts while moving only
    # semantic border ownership to the shared helper.
    assert 'Validation Error' in source
    assert 'reset_password_allowed' in source
    assert "user.auth_source == 'database'" in source
    assert "'Provider ready' if identity_context.provider_enabled else 'Provider disabled'" in source
    assert 'Editing Your Own Profile' in source
    assert 'form.hidden_tag()' in source
    assert 'surface_ui.block_classes()' in source


def test_user_form_semantic_border_debt_is_fully_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
