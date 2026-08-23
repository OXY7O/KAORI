#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
INLINE_SCRIPT = re.compile(r'<script\b', re.I)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    templates = sorted((ROOT / 'app/templates/intelligence').rglob('*.html'))
    require(bool(templates), 'Intelligence templates are missing.', errors)
    for path in templates:
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        require(not ARBITRARY_TEXT.search(source), f'{relative}: arbitrary text size detected.', errors)
        require(not RAW_HEX.search(source), f'{relative}: raw hex color detected.', errors)
        require(not INLINE_SCRIPT.search(source), f'{relative}: inline script detected.', errors)

    workspace = read('app/templates/intelligence/components/_workspace.html')
    require(
        'text-base font-semibold leading-6 text-content-primary' in workspace,
        'Intelligence primary section title scale drifted from text-base/leading-6.',
        errors,
    )
    require(
        'text-sm leading-6 text-content-secondary' in workspace,
        'Intelligence primary section description scale drifted from text-sm/leading-6.',
        errors,
    )

    recommendation_summary = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    catalog_summary = read('app/templates/intelligence/partials/_catalog_summary.html')
    alert_summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    automation = read('app/templates/intelligence/automation_control.html')
    canonical_summary_grid = 'grid divide-y divide-outline-subtle sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4'
    for name, source in (
        ('Recommendation Summary', recommendation_summary),
        ('Rule Catalog Summary', catalog_summary),
        ('Alert Operations Summary', alert_summary),
        ('Automation Control Summary', automation),
    ):
        require('intelligence_ui.section(' in source, f'{name}: canonical Intelligence section wrapper missing.', errors)
        require(canonical_summary_grid in source, f'{name}: canonical four-metric summary grid missing.', errors)

    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    active_form = active.split('id="alert-operations-filter-form"', 1)[1].split('</form>', 1)[0]
    require('hx-trigger="change, input changed delay:350ms"' in active_form, 'Active Alert Queue local trigger contract drifted.', errors)
    require('from:select' not in active_form, 'Active Alert Queue must not listen to Operational Context selects.', errors)
    require('from:input' not in active_form, 'Active Alert Queue must not listen to external inputs.', errors)

    alert_workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    context_form = alert_workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]
    require('hx-indicator="#alert-intelligence-context-loading"' in context_form, 'Operational Context must own its loading indicator.', errors)
    require('#alert-operations-active-loading' not in context_form, 'Operational Context must not trigger Active Alert Queue loading.', errors)

    resolved = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    for marker in (
        'data-alert-verification-closure',
        'data-alert-verification-fields',
        'data-alert-verification-references',
        'data-alert-verification-actions',
    ):
        require(marker in resolved, f'Resolved Alert verification layout marker missing: {marker}.', errors)
    require('lg:grid-cols-12' in resolved, 'Resolved Alert verification layout must use the balanced 12-column composition.', errors)
    require('Operational References' in resolved, 'Resolved Alert verification references panel is missing.', errors)
    require('class="mt-4 grid gap-3 lg:grid-cols-2"' not in resolved, 'Legacy flat verification form returned.', errors)

    recommendation_detail = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    require('Operator Direction' in recommendation_detail, 'Recommendation Operator Direction is missing.', errors)
    require('bg-kaori-mist/50' not in recommendation_detail, 'Operator Direction dark/tinted background regression detected.', errors)

    telegram = read('app/integrations/delivery/notification_channels/providers/telegram.py')
    alert_notifications = read('app/intelligence/alert_intelligence/notifications.py')
    alert_templates = read('app/intelligence/alert_intelligence/templates.py')
    require("payload['parse_mode'] = 'HTML'" in telegram, 'Telegram HTML parse mode is missing.', errors)
    require('<a href=' in telegram, 'Telegram clickable HTML action is missing.', errors)
    require('def _notification_action_url(path: str) -> str | None:' in alert_notifications, 'Telegram/Alert action absolute URL helper is missing.', errors)
    require("'Telegram · Firing'" in alert_templates and "'Telegram · Resolved'" in alert_templates, 'Telegram built-in alert templates are missing.', errors)

    typography_contract = ROOT / 'tests/contracts/design/test_intelligence_typography_hierarchy_full_audit_20260823_contract.py'
    require(typography_contract.exists(), 'Full Intelligence typography hierarchy contract is missing.', errors)

    if errors:
        print('FAIL — KAORI Intelligence Final Lock')
        for error in errors:
            print(f'- {error}')
        return 1

    print(f'PASS — KAORI Intelligence Final Lock ({len(templates)} templates checked)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
