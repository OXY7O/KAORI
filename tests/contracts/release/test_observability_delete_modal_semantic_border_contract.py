from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTMANAGER_TEMPLATE = (
    ROOT
    / 'app'
    / 'templates'
    / 'integrations'
    / 'observability'
    / 'alert_source'
    / 'providers'
    / 'alertmanager'
    / 'partials'
    / '_delete_confirmation_modal.html'
)
METRICS_SOURCE_TEMPLATE = (
    ROOT
    / 'app'
    / 'templates'
    / 'integrations'
    / 'observability'
    / 'metrics_source'
    / 'partials'
    / '_delete_confirmation_modal.html'
)
SHARED_RUNTIME_PATH = ROOT / 'app' / 'static' / 'js' / 'destructive_confirmation_modal.js'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)
TARGETS = {
    ALERTMANAGER_TEMPLATE: (
        'alertmanager-delete-modal',
        'data-destructive-confirmation-modal',
        'data-destructive-modal-close',
        '#alertmanager-scope-workspace',
    ),
    METRICS_SOURCE_TEMPLATE: (
        'metrics-source-delete-modal',
        'data-destructive-confirmation-modal',
        'data-destructive-modal-close',
        '#metrics-source-scope-workspace',
    ),
}


def test_observability_delete_modals_use_shared_critical_border_authority() -> None:
    runtime = SHARED_RUNTIME_PATH.read_text(encoding='utf-8')

    for template_path, markers in TARGETS.items():
        source = template_path.read_text(encoding='utf-8')

        assert '{% import "components/operational_callout.html" as operational_callout %}' in source
        assert source.count("operational_callout.semantic_border_classes('critical')") == 2
        assert SEMANTIC_BORDER.findall(source) == []
        assert 'role="dialog"' in source
        assert 'aria-modal="true"' in source
        assert 'hx-swap="outerHTML"' in source
        assert 'data-operation-submit' in source
        assert 'data-loading-label="Deleting..."' in source
        assert 'data-lucide="trash-2"' in source
        for marker in markers:
            assert marker in source

    assert "event.key === 'Escape'" in runtime
    assert 'opener?.focus()' in runtime


def test_observability_delete_modal_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))

    for template_path in TARGETS:
        relative = template_path.relative_to(ROOT).as_posix()
        assert relative not in payload['files']
