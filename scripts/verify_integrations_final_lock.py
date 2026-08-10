#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INTEGRATION_TEMPLATE_ROOTS = (
    Path('app/templates/integrations'),
    Path('app/templates/prometheus'),
    Path('app/templates/alertmanager'),
)

RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)
INLINE_STYLE = re.compile(r'\bstyle\s*=', re.I)
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def integration_templates() -> list[Path]:
    paths: list[Path] = []
    for relative in INTEGRATION_TEMPLATE_ROOTS:
        base = ROOT / relative
        if base.exists():
            paths.extend(base.rglob('*.html'))
    return sorted(set(paths))


def main() -> int:
    errors: list[str] = []
    checked_templates = 0

    # Locked Integration templates must stay tokenized and free from inline UI debt.
    for path in integration_templates():
        checked_templates += 1
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        require(not RAW_HEX.search(source), f'{relative}: raw hex color is forbidden', errors)
        require(not RAW_PALETTE.search(source), f'{relative}: raw Tailwind palette utility is forbidden', errors)
        require(not INLINE_STYLE.search(source), f'{relative}: inline style is forbidden', errors)
        require(not INLINE_HANDLER.search(source), f'{relative}: inline DOM event handler is forbidden', errors)

    # Capability readiness is one shared presentation contract across all providers.
    readiness = read('app/templates/integrations/components/_capability_readiness.html')
    require('data-kaori-capability-readiness' in readiness, 'Shared capability readiness marker is missing', errors)
    require('progress_bar.bar(' in readiness, 'Capability readiness must use the shared progress bar', errors)
    for relative in (
        'app/templates/integrations/kubernetes/partials/_capability_workspace.html',
        'app/templates/prometheus/partials/_detail_validation_content.html',
        'app/templates/alertmanager/partials/_detail_validation_content.html',
    ):
        source = read(relative)
        require(
            'integrations/components/_capability_readiness.html' in source,
            f'{relative}: must import shared capability readiness',
            errors,
        )
        require(
            'capability_readiness.render(' in source, f'{relative}: must render shared capability readiness', errors
        )

    # Capability registries use real HTMX interaction + one shared loading bar.
    registry_contracts = (
        (
            'app/templates/integrations/kubernetes/partials/_capability_registry.html',
            'kubernetes-capability-loading',
            False,
        ),
        ('app/templates/prometheus/partials/_capability_registry.html', 'prometheus-capability-loading', True),
        ('app/templates/alertmanager/partials/_capability_registry.html', 'alertmanager-capability-loading', True),
    )
    fake_loading_tokens = (
        'registryLoading:',
        'showRegistryLoading()',
        'loadingTimer:',
        'setTimeout(() => { registryLoading',
        'x-show="registryLoading"',
    )
    provider_registry_backend = read('app/integrations/capability_registry.py')
    common_pagination = read('app/common/pagination.py')
    require(
        'allowed_per_page=PER_PAGE_OPTIONS' in provider_registry_backend,
        'Provider capability registries must use shared PER_PAGE_OPTIONS',
        errors,
    )
    require(
        'PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)' in common_pagination,
        'Canonical KAORI page-size options drifted from 5/10/25/50',
        errors,
    )

    for relative, indicator_id, uses_variable_id in registry_contracts:
        source = read(relative)
        require('components/loading_bar.html' in source, f'{relative}: must import shared loading bar', errors)
        if uses_variable_id:
            require(
                f"loading_id = '{indicator_id}'" in source or f'loading_id = "{indicator_id}"' in source,
                f'{relative}: canonical loading id drifted',
                errors,
            )
            require(
                'loading_bar.render(loading_id' in source,
                f'{relative}: must render canonical loading indicator',
                errors,
            )
            require(
                'hx-indicator="#{{ loading_id }}"' in source,
                f'{relative}: registry requests must target canonical loading indicator',
                errors,
            )
        else:
            require(
                f"loading_bar.render('{indicator_id}'" in source,
                f'{relative}: must render canonical loading indicator',
                errors,
            )
            require(
                f'hx-indicator="#{indicator_id}"' in source,
                f'{relative}: registry requests must target canonical loading indicator',
                errors,
            )
        require('components/pagination.html' in source, f'{relative}: must use shared pagination', errors)
        require(
            'pagination.allowed_per_page' in source,
            f'{relative}: page-size selector must render server-owned allowed_per_page',
            errors,
        )
        for token in fake_loading_tokens:
            require(token not in source, f'{relative}: synthetic local loading state is forbidden ({token})', errors)

    # Record-detail actions and modals are shared; registry details may not recreate local geometry.
    actions = read('app/templates/integrations/components/_record_actions.html')
    require(
        '{{ table_ui.action_classes() }}' in actions,
        'Integration View More must use shared table action classes',
        errors,
    )
    require(
        'data-lucide="chevron-right"' in actions,
        'Integration View More must use quiet chevron-right iconography',
        errors,
    )
    require(
        'panel-top-open' not in actions, 'Integration View More must not restore oversized panel iconography', errors
    )
    require("role='record'" in actions, 'Shared View More macro must preserve optional role compatibility', errors)

    runtime_modal = read('app/templates/integrations/components/_runtime_observation_modal.html')
    require(
        'record_detail_modal.render(' in runtime_modal,
        'Runtime Observation must use shared record-detail modal shell',
        errors,
    )
    require("size='standard'" in runtime_modal, 'Runtime Observation modal must use standard size', errors)
    require(
        '<dialog' not in runtime_modal, 'Runtime Observation content must not own a standalone dialog shell', errors
    )
    require(
        'Diagnostic Review' in runtime_modal,
        'Runtime Observation modal must retain one Diagnostic Review boundary',
        errors,
    )
    require(
        'Recommended Action' in runtime_modal,
        'Runtime Observation diagnostic review must retain recommended action guidance',
        errors,
    )

    runtime_overview = read('app/templates/integrations/partials/_runtime_overview.html')
    require(
        'record_actions.view_more(' in runtime_overview,
        'Integration Runtime Overview must use shared View More',
        errors,
    )
    require(
        'expandable_row' not in runtime_overview and 'Hide Details' not in runtime_overview,
        'Runtime Overview inline detail expansion is forbidden',
        errors,
    )
    require('table-fixed' in runtime_overview, 'Runtime Overview must remain a fixed-layout KAORI table', errors)

    # Runtime detail workspaces remain full-width decision/evidence surfaces.
    for relative in (
        'app/templates/prometheus/partials/_runtime_panel.html',
        'app/templates/alertmanager/partials/_runtime_panel.html',
    ):
        source = read(relative)
        require(
            'integrations/components/_runtime_decision.html' in source,
            f'{relative}: must use shared runtime decision surface',
            errors,
        )
        require(
            'runtime_decision.render(' in source, f'{relative}: must render shared runtime decision surface', errors
        )
        require('xl:sticky' not in source, f'{relative}: sticky Runtime Decision rail is forbidden', errors)

    kubernetes_runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    require(
        'data-kaori-runtime-decision-summary' in kubernetes_runtime,
        'Kubernetes runtime decision summary marker is missing',
        errors,
    )
    require(
        'data-kaori-runtime-evidence-workspace' in kubernetes_runtime,
        'Kubernetes runtime evidence workspace marker is missing',
        errors,
    )
    require(
        'data-kaori-runtime-primary-finding' in kubernetes_runtime,
        'Kubernetes runtime primary finding must remain concise and explicit',
        errors,
    )

    # Configuration is the deliberate side-rail exception and must stay shared + symmetric.
    config_decision = read('app/templates/integrations/components/_configuration_decision.html')
    require(
        'data-kaori-configuration-decision-side' in config_decision,
        'Shared Configuration Decision side panel marker is missing',
        errors,
    )
    require(
        'flex h-full min-h-full flex-col self-stretch' in config_decision,
        'Configuration Decision must stretch with the working form',
        errors,
    )
    require(
        'operational_effects=none' in config_decision,
        'Configuration Decision must support optional Operational Effects evidence',
        errors,
    )
    require(
        'validation_boundary=none' in config_decision,
        'Configuration Decision must support optional Validation Boundary evidence',
        errors,
    )
    require(
        'Operational Effects' in config_decision, 'Configuration Decision Operational Effects block is missing', errors
    )
    require(
        'Validation Boundary' in config_decision, 'Configuration Decision Validation Boundary block is missing', errors
    )
    require(
        'xl:sticky' not in config_decision, 'Configuration Decision must not become a mismatched sticky rail', errors
    )
    for provider in ('prometheus', 'alertmanager'):
        relative = f'app/templates/{provider}/partials/_detail_configuration.html'
        source = read(relative)
        require(
            'configuration_decision.side_panel(' in source,
            f'{relative}: must use shared Configuration Decision side panel',
            errors,
        )
        require(
            'grid-cols-[minmax(0,1fr)_25rem]' in source,
            f'{relative}: canonical desktop configuration rail width drifted',
            errors,
        )
        require(
            'items-stretch' in source, f'{relative}: configuration surfaces must remain vertically symmetric', errors
        )
        require('embedded=true' in source, f'{relative}: Save Changes must remain an embedded footer action', errors)
    prometheus_configuration = read('app/templates/prometheus/partials/_detail_configuration.html')
    for required in (
        "('Save Changes', 'Resets technical readiness.')",
        "('Test Connection', 'Proves transport reachability only.')",
        "('Full Validation', 'Rebuilds capability evidence.')",
        "('Consumer Use', 'Requires eligible scope bindings.')",
        "('Transport Check', 'Test Connection')",
        "('Capability Contract', 'Full Validation')",
        "('Consumer Eligibility', 'Scope Binding')",
        "('Operational Use', 'Source Resolution')",
        'Prometheus executes metric queries. KAORI governs source selection, validation evidence, bindings, and consumer eligibility.',
    ):
        require(
            required in prometheus_configuration,
            f'Prometheus Configuration Decision density contract missing: {required}',
            errors,
        )

    # Provider detail tabs use one shared controller.
    tab_controller = read('app/static/js/integration_workspace_tabs.js')
    layout = read('app/templates/layouts/app.html')
    require('window.integrationWorkspaceTabs' in tab_controller, 'Shared provider tab controller is missing', errors)
    require(
        'integration_workspace_tabs.js' in layout, 'Application layout must load shared provider tab controller', errors
    )
    for provider in ('prometheus', 'alertmanager'):
        source = read(f'app/templates/{provider}/instance_detail.html')
        require('integrationWorkspaceTabs(' in source, f'{provider}: detail tabs must use shared controller', errors)
        require(
            'binding_rows|default([])' in source,
            f'{provider}: binding badge must count registered binding_rows',
            errors,
        )
        require(
            'scope_bindings|default([])' not in source,
            f'{provider}: stale scope_bindings badge fallback is forbidden',
            errors,
        )

    # Top-level registries stay scan-friendly and do not force desktop horizontal scrolling.
    registry_width_checks = (
        ('app/templates/integrations/kubernetes/partials/_registry.html', ('min-w-[1040px]', 'min-w-[840px]')),
        ('app/templates/integrations/prometheus/partials/_inventory_content.html', ('min-w-[1080px]',)),
        ('app/templates/integrations/alertmanager/partials/_inventory_content.html', ('min-w-[1040px]',)),
    )
    for relative, forbidden_widths in registry_width_checks:
        source = read(relative)
        require('table-fixed' in source, f'{relative}: top-level registry must use fixed proportional columns', errors)
        for token in forbidden_widths:
            require(token not in source, f'{relative}: forced desktop registry width is forbidden ({token})', errors)

    # RBAC baseline and optional Secret access remain separate by design.
    rbac = read('app/templates/integrations/kubernetes/partials/_minimum_validation_rbac.html')
    require(
        'components/workspace_tabs.html' in rbac and 'workspace_tabs.render(' in rbac,
        'Minimum Validation RBAC modal must use shared tabs',
        errors,
    )
    require(
        'Baseline Validation Reader' in rbac and 'Optional Secret Reader' in rbac,
        'Both RBAC evidence boundaries must remain explicit',
        errors,
    )
    baseline_start = rbac.find('id="minimum-rbac-panel-baseline"')
    optional_start = rbac.find('id="minimum-rbac-panel-secret"')
    baseline_rbac = (
        rbac[baseline_start:optional_start] if baseline_start >= 0 and optional_start > baseline_start else rbac
    )
    require('resources: ["secrets"]' not in baseline_rbac, 'Baseline validation RBAC must exclude Secrets', errors)
    optional_rbac = rbac[optional_start:] if optional_start >= 0 else ''
    require(
        'kind: Role' in optional_rbac and 'kind: RoleBinding' in optional_rbac,
        'Optional Secret reader must stay namespace-scoped',
        errors,
    )

    # Canonical Kubernetes navigation must not regress to the retired cluster list endpoint.
    kubernetes_detail = read('app/templates/integrations/kubernetes/detail.html')
    require(
        "url_for('integrations.kubernetes')" in kubernetes_detail,
        'Kubernetes detail must return to Integration registry',
        errors,
    )
    require(
        'cluster.list_clusters' not in kubernetes_detail,
        'Kubernetes detail must not reference retired cluster.list_clusters endpoint',
        errors,
    )

    # Shared operational feedback must stay script-owned and inline-style free.
    toast = read('app/templates/components/operational_toast.html')
    toast_js = read('app/static/js/operational_toasts.js')
    require('data-operational-toast-timer' in toast, 'Operational toast timer marker is missing', errors)
    require('style=' not in toast, 'Operational toast must remain free from inline timer style', errors)
    require(
        'timerBar.animate' in toast_js and 'scaleX(0)' in toast_js,
        'Operational toast countdown must remain JavaScript-owned',
        errors,
    )

    # Known dead Integration-era templates may not return.
    obsolete = (
        'app/templates/integrations/partials/_runtime_detail_content.html',
        'app/templates/prometheus/partials/_analytics_readiness.html',
        'app/templates/integrations/kubernetes/partials/_runtime_history.html',
        'app/templates/integrations/partials/_binding_validation_posture.html',
        'app/templates/integrations/partials/_status_badge.html',
        'app/templates/prometheus/partials/_validation_response.html',
        'app/templates/alertmanager/partials/_operation_feedback_oob.html',
    )
    cleanup_script = read('scripts/cleanup_obsolete_files.sh')
    for relative in obsolete:
        require(
            not (ROOT / relative).exists(),
            f'Obsolete Integration compatibility template reintroduced: {relative}',
            errors,
        )
        require(
            f"'{relative}'" in cleanup_script,
            f'Cleanup script must retain obsolete Integration path: {relative}',
            errors,
        )

    # The final lock documentation is itself part of the contract.
    lock_doc = read('docs/design/KAORI_INTEGRATIONS_LOCK_V1.md')
    refinement_doc = read('docs/design/KAORI_INTEGRATIONS_LOCK_V1_1.md')
    audit_doc = read('docs/design/audits/KAORI_INTEGRATIONS_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    require('Status: Locked baseline' in lock_doc, 'Integration lock document must declare Locked baseline', errors)
    require(
        'Status: Locked refinement baseline' in refinement_doc,
        'Integration v1.1 refinement lock must declare Locked refinement baseline',
        errors,
    )
    require(
        'Configuration Decision rail density' in refinement_doc,
        'Integration v1.1 refinement lock must freeze Configuration Decision density',
        errors,
    )
    require(
        'Prometheus Configuration Decision' in audit_doc,
        'Integration v1.1 audit must record Prometheus Configuration Decision refinement',
        errors,
    )
    require(
        'KAORI Integrations Lock v1' in standard, 'Integration workspace standard must reference the final lock', errors
    )
    require(
        'KAORI Integrations Lock v1.1' in standard,
        'Integration workspace standard must reference the v1.1 refinement',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Integrations final lock v1.1 passed across '
        f'{checked_templates} provider templates: shared capability/readiness, HTMX registry loading, '
        'runtime decision/evidence, modal detail, dense configuration side decisions, registered binding counts, '
        'RBAC separation, responsive registries, operational feedback, and obsolete-template cleanup are frozen.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
