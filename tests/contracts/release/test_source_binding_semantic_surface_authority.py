from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'integrations' / 'bindings' / 'partials' / '_workspace.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'

RAW_SEMANTIC_BORDERS = (
    'border-status-critical-border',
    'border-status-normal-border',
    'border-status-warning-border',
)


def test_source_binding_workspace_delegates_semantic_border_ownership() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/operational_callout.html" as operational_callout %}' in source
    assert "operational_callout.semantic_border_classes('critical')" in source
    assert "operational_callout.semantic_border_classes('normal')" in source
    assert source.count("operational_callout.semantic_border_classes('warning')") == 2
    for token in RAW_SEMANTIC_BORDERS:
        assert token not in source


def test_source_binding_workspace_preserves_binding_contract_markers() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    required_markers = (
        '{% from "integrations/components/_semantic_status.html" import integration_status %}',
        'integration_status(scope_row.coverage_status, scope_row.coverage_label)',
        'hx-post="{{ url_for(provider.bind_endpoint, scope_key=cluster.id) }}"',
        'hx-target="#source-binding-workspace"',
        'hx-swap="outerHTML"',
        'hx-indicator="#source-binding-progress"',
        'name="csrf_token"',
        'name="source_id"',
        'name="selector_label"',
        'name="selector_value"',
        'provider.register_endpoint',
        'provider.registry_endpoint',
    )
    for marker in required_markers:
        assert marker in source


def test_source_binding_workspace_is_removed_from_style_debt_ledger() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
