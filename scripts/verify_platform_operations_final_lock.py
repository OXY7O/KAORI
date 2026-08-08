#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCK_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1.md'
LOCK_V1_1_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_1.md'
LOCK_V1_2_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_2.md'
LOCK_V1_3_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_3.md'
LOCK_V1_4_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_4.md'
LOCK_V1_5_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_5.md'
LOCK_V1_6_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_6.md'
LOCK_V1_7_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_7.md'
LOCK_V1_8_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_8.md'
DATA_LIFECYCLE_LOCK_DOC = ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1.md'
AUDIT_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_AUDIT_2026_08_08.md'
AUDIT_V1_1_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md'
AUDIT_V1_2_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md'
AUDIT_V1_3_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_3_AUDIT_2026_08_08.md'
AUDIT_V1_4_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_4_AUDIT_2026_08_08.md'
AUDIT_V1_5_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_5_AUDIT_2026_08_08.md'
AUDIT_V1_6_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_6_AUDIT_2026_08_08.md'
AUDIT_V1_7_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_7_AUDIT_2026_08_08.md'
AUDIT_V1_8_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_8_AUDIT_2026_08_08.md'
DATA_LIFECYCLE_AUDIT_DOC = ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_AUDIT_2026_08_08.md'
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

    for doc in (LOCK_DOC, LOCK_V1_1_DOC, LOCK_V1_2_DOC, LOCK_V1_3_DOC, LOCK_V1_4_DOC, LOCK_V1_5_DOC, LOCK_V1_6_DOC, LOCK_V1_7_DOC, LOCK_V1_8_DOC, DATA_LIFECYCLE_LOCK_DOC, AUDIT_DOC, AUDIT_V1_1_DOC, AUDIT_V1_2_DOC, AUDIT_V1_3_DOC, AUDIT_V1_4_DOC, AUDIT_V1_5_DOC, AUDIT_V1_6_DOC, AUDIT_V1_7_DOC, AUDIT_V1_8_DOC, DATA_LIFECYCLE_AUDIT_DOC):
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

    data_lifecycle_index = read('app/templates/platform_operations/data_lifecycle/index.html')
    if 'components/framed_workspace_tabs.html' not in data_lifecycle_index or 'framed_workspace_tabs.render(' not in data_lifecycle_index:
        errors.append('Data Lifecycle must use shared Framed Workspace Tabs')
    if 'Planned Domains' in data_lifecycle_index:
        errors.append('Data Lifecycle must expose only registered archive adapters, not Planned Domains placeholders')
    if "url_for('jobs.executions')" not in data_lifecycle_index:
        errors.append('Data Lifecycle must preserve Jobs & Executions as the canonical runtime evidence boundary')

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

    job_routes = read('app/jobs/routes.py')
    if "_execution_context(include_queue_activity=active_section == 'executions')" not in job_routes:
        errors.append('Job Configuration must skip inactive Queue Activity topology inspection')
    job_workspace = read('app/templates/jobs/configuration/_job_workspace.html')
    if 'sync_progress' in job_workspace or '_quick_sync_status.html' in job_workspace or 'sync_progress' in job_routes:
        errors.append('Job Configuration must not reintroduce Inventory Sync progress toasts')
    configuration_workspace = read('app/templates/jobs/configuration/_workspace.html')
    if 'Planned Job Definitions' in configuration_workspace:
        errors.append('Job Configuration must list registered jobs only; Planned Job Definitions is retired')
    if 'Centralized orchestration with domain-owned execution.' not in configuration_workspace:
        errors.append('Job Configuration compact orchestration helper copy is missing')
    materialization_job = read('app/templates/jobs/configuration/definitions/_materialization_job.html')
    if 'Keep the last successful result available.' not in materialization_job:
        errors.append('Materialization stale-fallback helper copy must remain compact')
    for relative in (
        'app/templates/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/jobs/configuration/definitions/tls_certificate_sync.html',
        'app/templates/jobs/configuration/definitions/_materialization_job.html',
    ):
        source = read(relative)
        if 'Policy Timeline' not in source or 'overflow-hidden rounded-xl border border-outline-subtle bg-surface-card' not in source:
            errors.append(f'Job Configuration clear Policy Timeline surface missing: {relative}')
    report_schedule = read('app/templates/jobs/configuration/definitions/report_schedule.html')
    if 'article class="rounded-xl border border-outline-subtle bg-surface-card p-4"' not in report_schedule:
        errors.append('Report delivery-channel cards must use the clear KAORI card surface')

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

    reveal_policy = read('app/kubernetes_operations/secrets/reveal_policy.py')
    for required in (
        'class NamespaceSourceSnapshot:',
        'def cluster_reveal_readiness_evidence(',
        "'credential_configured': credential_configured",
        "state='unavailable'",
        "live_state = 'unknown'",
        'get_namespace_source_snapshot(cluster, refresh=refresh_source)',
        'verify_live_namespace(cluster, normalized_namespace)',
    ):
        if required not in reveal_policy:
            errors.append(f'Secret Reveal v1.3 readiness/source contract missing: {required}')

    secret_service = read('app/platform_operations/kubernetes/secret_reveal/service.py')
    for required in (
        'refresh_namespace_source: bool = False',
        "row['live_state'] == 'missing'",
        "row['live_state'] == 'unknown'",
        "'namespace_source': namespace_source_context",
        "'selected_cluster_readiness': selected_cluster_readiness",
    ):
        if required not in secret_service:
            errors.append(f'Secret Reveal v1.3 presentation contract missing: {required}')

    kubernetes_routes = read('app/platform_operations/kubernetes/routes.py')
    if "refresh_namespace='1'" not in kubernetes_routes:
        errors.append('Secret Reveal initial lazy load must explicitly refresh the namespace source')

    namespace_section = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html')
    for required in (
        'Live Namespace Source Unavailable',
        'Last Refreshed',
        'refresh_namespace=1',
        'data-lucide="refresh-cw"',
    ):
        if required not in namespace_section:
            errors.append(f'Secret Reveal live-source evidence missing: {required}')
    if 'refresh_namespace' in namespace_section.split('hx-trigger=', 1)[1].split('class=', 1)[0]:
        errors.append('Secret Reveal search/filter trigger must not request a live namespace refresh')

    for required in (
        '>Live Namespace<',
        '>Set Policy<',
        "live_label = 'Available'",
        "else 'Unknown'",
        'x-data="{ initial:',
        ':disabled="current === initial"',
        "value != 'disabled' and (not selected_cluster_ready or row.live_state != 'available')",
    ):
        if required not in namespace_table:
            errors.append(f'Secret Reveal namespace-row contract missing: {required}')

    cluster_workspace = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    for required in (
        'Cluster Credential',
        'selected_cluster_readiness.credential_configured',
        'All three cluster prerequisites must be satisfied.',
        'bg-surface-card shadow-sm xl:col-span-5',
        'Policies activate only when cluster readiness is satisfied.',
        'secret-reveal-selected-cluster-posture',
        'hx-swap-oob="outerHTML"',
    ):
        if required not in cluster_workspace:
            errors.append(f'Secret Reveal cluster-readiness contract missing: {required}')
    if '<aside class="overflow-hidden rounded-2xl border border-kaori-primary bg-kaori-primary' in cluster_workspace:
        errors.append('Secret Reveal Kubernetes Boundary must not return to a solid Violet surface')

    for required in (
        'Protection Boundary',
        'Step-up Authentication',
        'Independent Approval',
        'Namespace Policy',
        'Kubernetes RBAC',
        'secret-reveal-protected-cluster-count',
        'secret-reveal-enabled-namespace-count',
        'secret-reveal-selected-cluster-posture',
    ):
        if required not in secret_workspace:
            errors.append(f'Secret Reveal compact posture/boundary contract missing: {required}')

    cluster_workspace = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    for evidence in ('Kubernetes RBAC', 'Step-up', 'Approval'):
        if evidence.lower() not in cluster_workspace.lower() and evidence.lower() not in secret_workspace.lower():
            errors.append(f'Secret Reveal protected boundary evidence missing: {evidence}')

    protected_reveal_service = read('app/kubernetes_operations/secrets/reveal_service.py')
    for required in (
        'cluster_reveal_readiness,',
        'get_configured_enabled_namespace_names,',
        'get_enabled_namespace_names,',
        'get_namespace_policy,',
        'configured_names = get_configured_enabled_namespace_names(normalized_cluster_id)',
        'namespaces = get_enabled_namespace_names(normalized_cluster_id)',
        'namespace_policy = get_namespace_policy(cluster.id, target.namespace)',
        'current_policy = get_namespace_policy(record.cluster_id, record.namespace)',
        'current_policy != record.policy',
    ):
        if required not in protected_reveal_service:
            errors.append(f'Secret Reveal v1.5 cross-workspace authority missing: {required}')

    protected_live_service = read('app/kubernetes_operations/secrets/live_service.py')
    verified_namespace_block = protected_live_service.split('def list_verified_namespaces(', 1)[1].split('def list_live_secrets(', 1)[0] if 'def list_verified_namespaces(' in protected_live_service else ''
    for required in (
        'api.read_namespace(name=namespace)',
        'if status == 404:',
        'without broad Secret list/watch access',
    ):
        if required not in verified_namespace_block:
            errors.append(f'Secret Reveal configured-only namespace verification missing: {required}')
    if '.list_namespace()' in verified_namespace_block:
        errors.append('Protected Reveal configured namespace verification must not require broad Namespace LIST')

    secret_settings_routes = read('app/platform_operations/kubernetes/secret_reveal/routes.py')
    for required in (
        'queue_feedback=False',
        'queue_operational_feedback(operation_feedback)',
        "'components/operational_toast.html'",
        'toast_oob=True',
        'workspace_html + feedback_html',
    ):
        if required not in secret_settings_routes:
            errors.append(f'Secret Reveal immediate HTMX feedback contract missing: {required}')

    if '<span class="font-semibold text-content-secondary">Rows</span>' not in namespace_table:
        errors.append('Secret Reveal Namespace Policies pagination must include the visible Rows label')

    request_status = read('app/templates/kubernetes_operations/secrets/_reveal_request_status.html')
    if "{{ 'Request' if my_reveal_pagination.total == 1 else 'Requests' }}" not in request_status:
        errors.append('Protected Reveal pagination must use Title Case Request/Requests')
    if 'aria-label="Rows Per Page"' not in request_status:
        errors.append('Protected Reveal pagination must use Title Case Rows Per Page accessibility copy')
    if 'uppercase tracking-wide' in request_status or 'hover:bg-kaori-soft' in request_status:
        errors.append('Protected Reveal request registry must remain Title Case and neutral-first in dark mode')

    request_form = read('app/templates/kubernetes_operations/secrets/_reveal_request_form.html')
    if 'rounded-xl bg-kaori-primary text-white' in request_form:
        errors.append('Protected Reveal informational request icon must not use a solid Bright Violet surface')
    if 'space-y-1 text-xs leading-5 text-content-secondary' not in request_form:
        errors.append('Protected Reveal request guidance must use neutral content text')

    protected_reveal_page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    protected_reveal_service = read('app/kubernetes_operations/secrets/reveal_service.py')
    context_rail = read('app/templates/components/context_rail.html')
    for required in (
        'KUBERNETES_SECRET_REVEAL_ENABLED=true',
        'Protected Reveal globally disabled',
        'configured_reveal_namespace_count',
        'Activation Tip',
        'selection is locked by the global kill switch',
        "context_rail.layout_classes('wide')",
        'context_rail.rail_classes()',
    ):
        if required not in protected_reveal_page:
            errors.append(f'Secret Reveal v1.7 global-gate/natural-height contract missing: {required}')
    for forbidden in (
        "context_rail.layout_classes('wide', 'stretch')",
        'context_rail.rail_classes(true)',
        "extra_classes='h-full'",
    ):
        if forbidden in protected_reveal_page:
            errors.append(f'Secret Reveal v1.7 must keep Protected Reveal panels content-driven: {forbidden}')
    for required in (
        'SecretRevealNamespacePolicy',
        "SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))",
        "'configured_reveal_namespace_count': configured_reveal_namespace_count",
    ):
        if required not in protected_reveal_service:
            errors.append(f'Secret Reveal v1.6 configured-policy evidence missing: {required}')
    for required in (
        "layout_classes(width='default')",
        'xl:items-start',
        'rail_classes()',
    ):
        if required not in context_rail:
            errors.append(f'Secret Reveal v1.7 shared context-rail contract missing: {required}')
    for forbidden in ('items-stretch', 'rail_classes(fill=false)', "align='start'"):
        if forbidden in context_rail:
            errors.append(f'Secret Reveal v1.7 shared context rail must return to natural-height geometry: {forbidden}')
    for required in (
        'grid gap-4 p-5 sm:p-6 xl:grid-cols-12',
        'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm xl:col-span-7',
        'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm xl:col-span-5',
        'grid gap-3 p-4 sm:grid-cols-2 sm:p-5',
    ):
        if required not in cluster_workspace:
            errors.append(f'Secret Reveal v1.7 administration natural-height contract missing: {required}')
    for forbidden in ('grid items-stretch gap-4', 'flex h-full flex-col overflow-hidden rounded-2xl', 'grid flex-1 gap-3'):
        if forbidden in cluster_workspace:
            errors.append(f'Secret Reveal v1.7 administration panels must remain content-driven: {forbidden}')

    if 'bg-white/70' in secret_workspace:
        errors.append('Secret Reveal administration must not use hardcoded light-only callout surfaces')
    if 'hover:bg-kaori-soft/40' in namespace_section or 'bg-kaori-soft/70' in namespace_table or 'hover:bg-kaori-soft/40' in namespace_table:
        errors.append('Secret Reveal administration tables and refresh controls must remain neutral-first in dark mode')

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
        'KAORI Platform Operations Final Lock v1.8 passed: Kubernetes Administration and Jobs & Executions '
        'use shared tabs, Title Case, bounded execution attention, expandable execution evidence, worker readiness, '
        'activity-center background feedback, lean Job Configuration rendering, clear configuration surfaces, '
        'tri-state Secret Reveal live evidence, snapshot-backed namespace filtering, explicit credential readiness, '
        'HTMX-owned registry controls, shared Secret Reveal policy authority, neutral-first protected-reveal dark surfaces, '
        'Title Case reveal pagination with Rows labels, immediate HTMX mutation feedback, configured-only live namespace verification, explicit global kill-switch diagnostics with compact activation tips, natural-height Secret Reveal side panels, protected Secret Reveal guardrails, Platform Operations-owned Data Lifecycle routing/RBAC/shared tabs/archive evidence, canonical Jobs execution boundaries, and permanent legacy cleanup.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
