#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCK_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1.md'
LOCK_V1_1_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_1.md'
AUDIT_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_AUDIT_2026_08_08.md'
AUDIT_V1_1_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md'
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
CLEANUP = ROOT / 'scripts/cleanup_obsolete_files.sh'
CORE_UI_LOCK = ROOT / 'scripts/verify_core_workspace_ui_lock.py'

TEMPLATE_ROOTS = (
    ROOT / 'app/templates/platform_operations',
    ROOT / 'app/templates/jobs',
)

RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)
RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
INLINE_STYLE = re.compile(r'\bstyle\s*=', re.I)
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)
UPPERCASE_UTILITY = re.compile(r'\buppercase\b')
TABLIST = re.compile(r'role=["\']tablist["\']', re.I)

OBSOLETE = (
    'app/templates/platform_operations/kubernetes/_tabs.html',
    'app/templates/jobs/executions/partials/_hero_context_metrics.html',
    'app/templates/jobs/executions/partials/_hero_metadata.html',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def template_files() -> list[Path]:
    result: list[Path] = []
    for root in TEMPLATE_ROOTS:
        if root.exists():
            result.extend(root.rglob('*.html'))
    return sorted(result)


def main() -> int:
    errors: list[str] = []

    for doc in (LOCK_DOC, LOCK_V1_1_DOC, AUDIT_DOC, AUDIT_V1_1_DOC):
        if not doc.exists():
            errors.append(f'missing lock artifact: {doc.relative_to(ROOT).as_posix()}')

    for path in template_files():
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        if RAW_HEX.search(source):
            errors.append(f'{relative}: raw hex color is forbidden')
        if RAW_PALETTE.search(source):
            errors.append(f'{relative}: raw Tailwind palette utility is forbidden')
        if ARBITRARY_TEXT.search(source):
            errors.append(f'{relative}: arbitrary text size is forbidden')
        if INLINE_STYLE.search(source):
            errors.append(f'{relative}: inline style is forbidden')
        if INLINE_HANDLER.search(source):
            errors.append(f'{relative}: inline DOM event handler is forbidden')
        if UPPERCASE_UTILITY.search(source):
            errors.append(f'{relative}: visible Platform Operations labels must use Title Case')
        if TABLIST.search(source):
            errors.append(f'{relative}: page-local tablist is forbidden; use shared KAORI tabs')

    k8s_index = read('app/templates/platform_operations/kubernetes/index.html')
    if 'components/framed_workspace_tabs.html' not in k8s_index or 'framed_workspace_tabs.render(' not in k8s_index:
        errors.append('Kubernetes Administration must use shared Framed Workspace Tabs')
    for key in ('overview', 'secret-reveal'):
        if key not in k8s_index:
            errors.append(f'Kubernetes Administration tab missing: {key}')
    for keyboard in ('@keydown.arrow-right.prevent', '@keydown.arrow-left.prevent', '@keydown.home.prevent', '@keydown.end.prevent'):
        shared = read('app/templates/components/framed_workspace_tabs.html')
        if keyboard not in shared:
            errors.append(f'Framed Workspace Tabs lost keyboard contract: {keyboard}')

    jobs_index = read('app/templates/jobs/index.html')
    if 'components/framed_workspace_tabs.html' not in jobs_index or 'framed_workspace_tabs.render(' not in jobs_index:
        errors.append('Jobs & Executions parent workspace must use shared Framed Workspace Tabs')

    execution_workspace = read('app/templates/jobs/executions/_workspace.html')
    shared_tabs = read('app/templates/components/workspace_tabs.html')
    if 'components/workspace_tabs.html' not in execution_workspace or 'workspace_tabs.render(' not in execution_workspace:
        errors.append('Execution Workspace must use shared Integrated Workspace Tabs')
    if 'id="{{ prefix }}-tab-count-{{ tab_key }}"' not in shared_tabs:
        errors.append('Integrated Workspace Tabs must retain shared optional count badge ownership')
    if 'integrations/components/' in execution_workspace:
        errors.append('Jobs must not depend on Integration-specific presentation components')

    status_refresh = read('app/templates/jobs/executions/partials/_status_refresh.html')
    for key in ('active', 'registry', 'queues'):
        if f'id="execution-tab-count-{key}"' not in status_refresh:
            errors.append(f'Execution live OOB count missing: {key}')

    active_jobs = read('app/templates/jobs/executions/partials/_active_jobs.html')
    if 'hx-trigger="every 5s"' not in active_jobs or '{% if active_job_rows %}hx-get=' in active_jobs:
        errors.append('Active Work polling must remain live even when no active execution is rendered')
    if "('Active Attention', job_stats.active_attention)" not in active_jobs:
        errors.append('Active Work must distinguish active intervention from recent terminal attention')

    job_presentation = read('app/jobs/presentation.py')
    for required in (
        "_ACTIVE_ATTENTION_STATUSES = ('retrying', 'cancel_requested')",
        "_RECENT_ATTENTION_STATUSES = ('failed', 'partially_succeeded', 'expired')",
        'JobExecution.completed_at >= cutoff',
        'topology = inspect_celery_topology() if queue_names else None',
        'get_queue_readiness(queue_name, topology=topology)',
        'include_queue_activity: bool = True',
    ):
        if required not in job_presentation:
            errors.append(f'Jobs v1.1 operational semantics missing: {required}')

    registry = read('app/templates/jobs/executions/partials/_registry.html')
    for required in (
        'components/loading_bar.html',
        'components/pagination.html',
        'components/table.html',
        'components/table_label.html',
        'hx-trigger="submit, change from:select"',
        'hx-trigger="change from:select"',
        "pagination_ui.resource_name('Executions'",
        '<option value="5"',
        '<option value="10"',
        '<option value="25"',
        '<option value="50"',
        'expandable_row.toggle_button(',
        "url_for('jobs.execution_details'",
        'data-detail-content',
    ):
        if required not in registry:
            errors.append(f'Execution Registry final contract missing: {required}')
    if "('Total Records', job_stats.total)" in registry:
        errors.append('Execution Registry must not reintroduce unfiltered global metric strips')

    execution_detail = read('app/templates/jobs/executions/partials/_execution_details.html')
    for required in ('Execution Identity', 'Scope & Ownership', 'Lifecycle', 'Result & Failure Evidence', 'Result Summary'):
        if required not in execution_detail:
            errors.append(f'Execution detail evidence contract missing: {required}')
    if 'payload_json' in execution_detail:
        errors.append('Execution detail must not render raw execution payloads')

    queue_activity = read('app/templates/jobs/executions/partials/_queue_activity.html')
    for required in ('Worker Readiness', "fragment='queues'", 'worker_readiness.description'):
        if required not in queue_activity:
            errors.append(f'Queue Activity worker-readiness contract missing: {required}')

    if 'Operational Attention' not in jobs_index or 'job_stats.attention + configuration_stats.attention' not in jobs_index:
        errors.append('Jobs hero must present combined Operational Attention')

    namespace_table = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')
    if 'min-w-[980px]' in namespace_table or '<div class="overflow-x-auto">' in namespace_table:
        errors.append('Namespace Policies must not force desktop horizontal scrolling')
    for width in ('w-[38%]', 'w-[16%]', 'w-[20%]', 'w-[26%]'):
        if width not in namespace_table:
            errors.append(f'Namespace Policies proportional column contract missing: {width}')
    if 'data-kaori-auto-submit' not in namespace_table:
        errors.append('Namespace Policies page-size control must retain shared auto-submit ownership')

    secret_workspace = read('app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html')
    if 'Global Reveal Remains Disabled' not in secret_workspace or 'KUBERNETES_SECRET_REVEAL_ENABLED=true' not in secret_workspace:
        errors.append('Secret Reveal global guardrail guidance must remain visible when disabled')

    cluster_workspace = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    for evidence in ('Kubernetes RBAC', 'Step-up', 'Approval'):
        if evidence.lower() not in cluster_workspace.lower() and evidence.lower() not in secret_workspace.lower():
            errors.append(f'Secret Reveal protected boundary evidence missing: {evidence}')

    for relative in OBSOLETE:
        if (ROOT / relative).exists():
            errors.append(f'obsolete Platform Operations path reintroduced: {relative}')
        if relative not in CLEANUP.read_text(encoding='utf-8'):
            errors.append(f'obsolete Platform Operations path missing from cleanup registry: {relative}')

    quality_gate = QUALITY_GATE.read_text(encoding='utf-8')
    if 'python scripts/verify_platform_operations_final_lock.py' not in quality_gate:
        errors.append('Platform Operations final-lock verifier is not release-gated')

    core_ui_lock = CORE_UI_LOCK.read_text(encoding='utf-8')
    for prefix in ("'app/templates/platform_operations/'", "'app/templates/jobs/'"):
        if prefix not in core_ui_lock:
            errors.append(f'generic locked-template verifier missing Platform Operations prefix: {prefix}')

    style_baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json')).get('files', {})
    platform_debt = [
        path for path in style_baseline
        if path.startswith('app/templates/platform_operations/') or path.startswith('app/templates/jobs/')
    ]
    if platform_debt:
        errors.append('Platform Operations must not carry accepted UI-style debt baseline entries: ' + ', '.join(sorted(platform_debt)))

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Platform Operations Final Lock v1.1 passed: Kubernetes Administration and Jobs & Executions '
        'use shared tabs, Title Case, bounded execution attention, expandable execution evidence, worker readiness, '
        'HTMX-owned registry controls, protected Secret Reveal guardrails, and permanent legacy cleanup.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
