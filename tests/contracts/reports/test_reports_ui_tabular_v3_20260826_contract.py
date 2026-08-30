from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_python_string(source: str, expected: str) -> bool:
    return any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and expected in node.value
        for node in ast.walk(ast.parse(source))
    )


def test_reports_operational_copy_is_compact_and_consistent() -> None:
    templates_service = read('app/reports/report_templates/service.py')
    storage_service = read('app/reports/storage/service.py')
    storage = read('app/templates/reports/storage/index.html')

    assert has_python_string(
        templates_service,
        'Manage protected system templates and reusable custom report structures for Analytics PDF/XLSX/CSV and Inventory XLSX/CSV.',
    )
    assert has_python_string(
        storage_service,
        'Review report storage readiness, integrity, and lifecycle ownership for PDF/XLSX/CSV artifacts.',
    )
    assert 'S3-compatible target for generated reports and verification evidence.' in storage


def test_template_registry_uses_compact_six_column_layout_without_horizontal_scroll() -> None:
    template = read('app/templates/reports/report_templates/index.html')
    registry = template.split('id="templates-registry"', 1)[1].split('data-template-detail-modal', 1)[0]

    assert 'min-w-[1240px]' not in registry
    assert '<div class="overflow-x-auto">' not in registry
    assert 'data-template-registry-table="compact-v3"' in registry
    for label in ('Template', 'Contract', 'Output', 'Sections', 'Ownership', 'Action'):
        assert f'>{label}</th>' in registry
    for removed in ('>Domain</th>', '>Family</th>', '>Report Type</th>'):
        assert removed not in registry
    assert '{{ template.domain_label }}' in registry
    assert '{{ template.family_label }}' in registry
    assert '{{ template.report_type_label }}' in registry


def test_storage_object_key_contract_is_readable_and_integrity_uses_action_cards() -> None:
    template = read('app/templates/reports/storage/index.html')

    assert 'data-storage-object-key-contract="readable"' in template
    object_key = template.split('data-storage-object-key-contract="readable"', 1)[1].split('</div>', 2)[0]
    assert 'whitespace-nowrap' not in object_key
    assert 'overflow-x-auto' not in object_key
    assert 'break-words' in object_key
    assert 'data-kaori-copy' in object_key

    integrity = template.split("{% elif payload.workspace == 'integrity' %}", 1)[1].split(
        "{% elif payload.workspace == 'retention' %}", 1
    )[0]
    assert 'data-storage-integrity-actions="action-cards"' in integrity
    assert 'data-storage-integrity-guidance="true"' not in integrity
    assert 'Artifact Integrity Scan' in integrity
    assert 'Read-only check of retained artifact references.' in integrity


def test_quick_actions_use_one_card_shell_and_include_jobs_executions() -> None:
    template = read('app/templates/components/navigation/navbar.html')
    quick = template.split('<!-- Quick actions -->', 1)[1].split('{% set activity_center', 1)[0]

    assert quick.count('data-quick-action-card="true"') == 4
    for title, badge in (
        ('Sync All Inventory', 'Inventory'),
        ('Generate Report', 'Reports'),
        ('Jobs &amp; Executions', 'Operations'),
        ('Alert Center', 'Intelligence'),
    ):
        assert title in quick
        assert f'>{badge}</span>' in quick
    assert "url_for('jobs.executions')" in quick
    assert 'Create a new operational report from a governed report contract.' in quick
    assert 'Review worker-backed executions, queues, and recent job outcomes.' in quick
    assert 'bg-status-warning-soft text-status-warning-text' not in quick
