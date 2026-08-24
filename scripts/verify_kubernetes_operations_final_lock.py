#!/usr/bin/env python3
"""Verify the final Kubernetes Operations CRUD, security, and release contracts."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MUTATION_TEMPLATES = (
    'app/templates/kubernetes/operations/configmaps/create.html',
    'app/templates/kubernetes/operations/configmaps/update.html',
    'app/templates/kubernetes/operations/configmaps/delete.html',
    'app/templates/kubernetes/operations/secrets/create.html',
    'app/templates/kubernetes/operations/secrets/replace.html',
    'app/templates/kubernetes/operations/secrets/delete.html',
    'app/templates/kubernetes/operations/secrets/reveal.html',
    'app/templates/kubernetes/operations/secrets/tls_rotation.html',
)
ROUTE_FILES = (
    'app/kubernetes/operations/configmaps/routes.py',
    'app/kubernetes/operations/secrets/crud_routes.py',
    'app/kubernetes/operations/secrets/reveal_routes.py',
    'app/kubernetes/operations/secrets/tls_routes.py',
)
RELEASE_EVIDENCE = (
    'tests/contracts/kubernetes/operations/test_kubernetes_operations_final_release_contract.py',
    'tests/unit/kubernetes/operations/test_operation_flow_unit.py',
    'tests/kubernetes/operations/test_route_authorization_characterization.py',
    'tests/integration/kubernetes/operations/test_live_runtime_boundary.py',
    'tests/security/kubernetes/operations/test_kubernetes_operations_security.py',
    'tests/rendering/kubernetes/operations/test_kubernetes_operations_rendering.py',
    'tests/e2e/kubernetes/operations/test_kubernetes_operations_smoke.py',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ''


def main() -> int:
    errors: list[str] = []

    root_routes = read('app/kubernetes/operations/routes.py')
    operation_flow = read('app/kubernetes/operations/operation_flow.py')
    cluster_required_template = read('app/templates/kubernetes/operations/cluster_required.html')
    shared_ui = read('app/templates/components/kubernetes_operation_ui.html')
    form_context = read('app/templates/components/form_with_context_rail.html')
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    pattern = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')
    configmap_readme = read('app/kubernetes/operations/configmaps/README.md')
    secret_readme = read('app/kubernetes/operations/secrets/README.md')

    require(
        '.before_request' not in root_routes,
        'Operations must not use a Blueprint before_request blocker.',
        errors,
    )
    require(
        'has_registered_clusters' not in root_routes,
        'Cluster readiness must be owned by the post-authorization operation decorator, not the root blueprint.',
        errors,
    )
    require(
        'components/cluster/_hero_blocked_context.html' in cluster_required_template
        and 'Operations Readiness' in cluster_required_template
        and '{{ requested_page_title }}' in cluster_required_template
        and '{{ requested_page_description }}' in cluster_required_template
        and '>Kubernetes Cluster Setup Required</h1>' not in cluster_required_template
        and 'Cluster Setup Required' in cluster_required_template,
        'Kubernetes Operations cluster prerequisite must use the canonical setup-blocked Hero context.',
        errors,
    )

    for token in (
        'def cluster_required[',
        'page_title: str | None = None',
        'page_description: str | None = None',
        'requested_page_title=page_title or operation_label',
        'requested_page_description=(',
        'has_registered_clusters()',
        "request.headers.get('HX-Request') == 'true'",
        "render_template('components/cluster/_onboarding_banner.html')",
    ):
        require(token in operation_flow, f'Operations cluster prerequisite is missing: {token}', errors)

    primary_identity_tokens = {
        'app/kubernetes/operations/configmaps/routes.py': (
            "page_title='ConfigMap Management'",
            "page_title='Create Kubernetes ConfigMap'",
            "page_title='Update ConfigMap'",
            "page_title='Delete ConfigMap'",
        ),
        'app/kubernetes/operations/secrets/crud_routes.py': (
            "page_title='Secret Management'",
            "page_title='Create Kubernetes Secret'",
            "page_title='Replace Kubernetes Secret Data'",
            "page_title='Delete Kubernetes Secret'",
        ),
        'app/kubernetes/operations/secrets/reveal_routes.py': ("page_title='Protected Kubernetes Secret Reveal'",),
        'app/kubernetes/operations/secrets/tls_routes.py': (
            "page_title='Rotate TLS Secret'",
            "page_title='Bulk TLS Secret Rotation'",
        ),
    }
    for relative, tokens in primary_identity_tokens.items():
        route_source = read(relative)
        for token in tokens:
            require(token in route_source, f'{relative} blocked page identity missing: {token}', errors)

    protected = 0
    for relative in ROUTE_FILES:
        tree = ast.parse(read(relative), filename=relative)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = [_decorator_name(decorator) for decorator in node.decorator_list]
            if 'cluster_required' not in decorators:
                continue
            protected += 1
            permission_indexes = [
                index
                for index, name in enumerate(decorators)
                if name in {'permission_required', 'any_permission_required'}
            ]
            require(bool(permission_indexes), f'{relative}:{node.name} must own an RBAC decorator.', errors)
            if permission_indexes:
                require(
                    min(permission_indexes) < decorators.index('cluster_required'),
                    f'{relative}:{node.name} must authorize before cluster readiness.',
                    errors,
                )
    require(
        protected >= 30,
        'Expected all ConfigMap/Secret/TLS/Reveal routes to use the cluster prerequisite.',
        errors,
    )

    for token in (
        'macro workspace_section',
        'macro guidance_panel',
        'data-kubernetes-operation-guidance',
        'macro workflow_control',
        'data-kubernetes-operation-workflow',
        'data-kubernetes-operation-guardrails',
        'components/operational_point_flow.html',
        'embedded=true',
    ):
        require(token in shared_ui, f'Shared Operations UI missing canonical token: {token}', errors)

    for token in (
        'grid gap-6 xl:grid-cols-12 xl:items-start',
        'min-w-0 xl:col-span-8',
        'min-w-0 space-y-4 xl:col-span-4 xl:sticky xl:top-5',
    ):
        require(token in form_context, f'Form + Right Context component missing canonical geometry: {token}', errors)

    form_context_pages = (
        'app/templates/kubernetes/operations/configmaps/create.html',
        'app/templates/kubernetes/operations/configmaps/update.html',
        'app/templates/kubernetes/operations/configmaps/delete.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/replace.html',
        'app/templates/kubernetes/operations/secrets/delete.html',
        'app/templates/kubernetes/operations/secrets/reveal.html',
    )
    for relative in form_context_pages:
        source = read(relative)
        for token in (
            'data-kubernetes-operation-layout="form-context-v1"',
            'components/form_with_context_rail.html',
            'form_context.layout_classes()',
            'form_context.main_classes()',
            'form_context.rail_classes()',
            'components/info_flow.html',
            'components/information_guide_card.html',
        ):
            require(token in source, f'{relative} Form + Right Context contract missing: {token}', errors)
        require(
            'workflow_control(' not in source,
            f'{relative} must keep workflow/safety guidance in the right context column instead of a full-width workflow card.',
            errors,
        )

    bulk_tls = read('app/templates/kubernetes/operations/secrets/tls_rotation.html')
    require(
        'data-kubernetes-operation-layout="full-width-v2"' in bulk_tls,
        'Bulk TLS rotation must retain its dedicated full-width reviewed workspace.',
        errors,
    )
    require(
        'workflow_control(' in bulk_tls,
        'Bulk TLS rotation must retain the full-width controlled workflow section.',
        errors,
    )

    single_tls = read('app/templates/kubernetes/operations/secrets/tls_rotate.html')
    require(
        'context_rail.html' not in single_tls,
        'Single TLS rotation must remain free of the retired content rail.',
        errors,
    )
    require(
        'Controlled Rotation & Governance Posture' in single_tls,
        'Single TLS rotation must retain the integrated Governance posture workspace.',
        errors,
    )

    secret_create = read('app/templates/kubernetes/operations/secrets/create.html')
    require(
        'grid gap-5 md:grid-cols-2' in secret_create and 'lg:grid-cols-2 xl:grid-cols-4' not in secret_create,
        'Secret Create Target & Identity must use the reviewed two-column, two-row field geometry.',
        errors,
    )
    reveal_page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    reveal_tabs = read('app/templates/components/content_tabs.html')
    require(
        'No eligible cluster. Review readiness or policy.' in reveal_page,
        'Protected Reveal empty-cluster guidance must use the compact reviewed wording.',
        errors,
    )
    reveal_script = read('app/static/js/secret_reveal_workspace.js')
    reveal_routes = read('app/kubernetes/operations/secrets/reveal_routes.py')
    reveal_service = read('app/kubernetes/operations/secrets/reveal_service.py')
    reveal_step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    for token in (
        'components/content_tabs.html',
        'content_tabs.render_controlled_links',
        "activeTab: '{{ active_reveal_view }}'",
        'setTab(tab)',
        "url.searchParams.set('reveal_view', tab)",
        'window.history.replaceState',
    ):
        require(token in reveal_page, f'Protected Reveal workspace tab contract missing: {token}', errors)
    require(
        'components/segmented_tabs.html' not in reveal_page,
        'Protected Reveal must use the approved Analytics-derived Content Tabs treatment, not Compact Segmented Tabs.',
        errors,
    )
    require(
        '@click.prevent="setTab(' in reveal_tabs
        and 'data-kaori-tab-fallback="server-navigation"' in reveal_tabs
        and 'href="{{ tab_href }}"' in reveal_tabs,
        'Protected Reveal Content Tabs must switch through Alpine while retaining server-navigation fallback.',
        errors,
    )
    for token in (
        'x-show="activeTab === \'new\'"',
        'x-show="activeTab === \'mine\'"',
        'x-bind:hidden="activeTab !== \'new\'"',
        'x-bind:hidden="activeTab !== \'mine\'"',
        '#my-secret-reveal-requests',
        '#pending-secret-reveal-approvals',
    ):
        require(token in reveal_page, f'Protected Reveal Alpine panel-state contract missing: {token}', errors)
    require(
        "information_guide_card.render('Reveal Safety Contract'" in reveal_page
        and "protected_reveal_guardrails, icon='shield-check', open_by_default=false" in reveal_page,
        'Protected Reveal Safety Contract must remain collapsed by default.',
        errors,
    )
    for token in (
        'const activePanel = (root) =>',
        '!panel.hidden',
        "querySelector('[data-reveal-poll-owner]')",
        'window.setInterval',
        'secret-reveal:tab-changed',
    ):
        require(token in reveal_script, f'Protected Reveal active-panel polling contract missing: {token}', errors)
    require(
        'viewState' not in reveal_script
        and 'selectTab' not in reveal_script
        and 'event.preventDefault' not in reveal_script,
        'Protected Reveal polling script must not duplicate Integrated Workspace Tab navigation ownership.',
        errors,
    )
    require(
        "reveal_view='new'" in reveal_page and "reveal_view='mine'" in reveal_page,
        'Protected Reveal peer tabs must expose server-owned reveal_view fallback URLs.',
        errors,
    )
    for token in (
        "request.args.get('reveal_view')",
        "'active_reveal_view': active_reveal_view",
        "reveal_view='mine'",
        "reveal_view='approvals'",
    ):
        require(token in reveal_routes, f'Protected Reveal route-state contract missing: {token}', errors)
    require(
        'Reveal Session Step-Up' in reveal_step_up and 'approved request is ready to be consumed' in reveal_step_up,
        'Protected Reveal step-up must remain in the approved-request consumption flow.',
        errors,
    )
    require(
        'query.enable_eagerloads(False).with_for_update(of=SecretRevealRequest)' in reveal_service
        and 'query = query.with_for_update()' not in reveal_service,
        'Protected Reveal one-time consumption must lock only the SecretRevealRequest row without joined eager loads.',
        errors,
    )
    require(
        'components/form_field.html' in reveal_step_up
        and 'sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end' in reveal_step_up
        and 'form_field.label_row(' in reveal_step_up
        and 'Current KAORI Password' in reveal_step_up
        and 'class="{{ form_field.input_classes() }}"' in reveal_step_up,
        'Protected Reveal step-up password and Verify Session action must share the canonical form-field baseline.',
        errors,
    )
    new_request_panel = reveal_page.split('data-secret-reveal-panel="new"', 1)[1].split(
        'data-secret-reveal-panel="mine"',
        1,
    )[0]
    require(
        'Reveal Session Step-Up' not in new_request_panel,
        'Protected Reveal New Request must not require step-up before request creation.',
        errors,
    )

    for obsolete in (
        'app/kubernetes/operations/secrets/routes.py',
        'app/templates/kubernetes/operations/_components.html',
    ):
        require(not (ROOT / obsolete).exists(), f'Legacy Operations file must remain removed: {obsolete}', errors)

    for source_name, source in (
        ('ConfigMap README', configmap_readme),
        ('Secret README', secret_readme),
        ('pattern', pattern),
    ):
        for retired_wording in ('shared 22rem wide', 'sticky right-column wrapper', 'sticky right column'):
            require(retired_wording not in source, f'{source_name} still documents retired rail wording.', errors)
    require(
        'Canonical Mutation Workspace — Task-Fit Layout v7' in pattern,
        'Operations design pattern must document the current task-fit layout policy.',
        errors,
    )
    require(
        'AuthZ → cluster prerequisite' in pattern,
        'Operations pattern must document AuthZ-first ordering.',
        errors,
    )

    for relative in RELEASE_EVIDENCE:
        require((ROOT / relative).exists(), f'Missing Operations release evidence: {relative}', errors)
        require(relative in coverage, f'Feature coverage manifest must require {relative}.', errors)

    require(
        'python scripts/verify_kubernetes_operations_final_lock.py' in quality_gate,
        'quality_gate.sh must run the Kubernetes Operations final-lock verifier.',
        errors,
    )
    require(
        'tests/kubernetes/operations' in quality_gate,
        'quality_gate.sh must run Kubernetes Operations functional characterization explicitly.',
        errors,
    )

    form_field = read('app/templates/components/form_field.html')
    replace_page = read('app/templates/kubernetes/operations/secrets/replace.html')
    replace_content = read('app/templates/kubernetes/operations/secrets/_replace_content_form.html')
    require(
        'min-h-6' in form_field and 'mt-2 h-10 w-full' in form_field,
        'Form Field Alignment contract drifted.',
        errors,
    )
    require(
        'replace-secret-apply-button' in replace_content and 'Replace Selected Data' in replace_content,
        'Secret Replace must render its apply action inside the HTMX-swapped content.',
        errors,
    )
    require(
        '{% if target and not target.immutable %}' not in replace_page,
        'Secret Replace page must not gate actions on stale parent target state.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Kubernetes Operations final-lock passed: AuthZ-first cluster prerequisites, '
        'task-appropriate ConfigMap/Secret mutation workspaces, reviewed Integration registration geometry, layered release evidence, '
        'and canonical shared workflow ownership are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
