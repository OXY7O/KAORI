#!/usr/bin/env python3
"""Verify the final Kubernetes Operations CRUD, security, and release contracts."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MUTATION_TEMPLATES = (
    'app/templates/kubernetes_operations/configmaps/create.html',
    'app/templates/kubernetes_operations/configmaps/update.html',
    'app/templates/kubernetes_operations/configmaps/delete.html',
    'app/templates/kubernetes_operations/secrets/create.html',
    'app/templates/kubernetes_operations/secrets/replace.html',
    'app/templates/kubernetes_operations/secrets/delete.html',
    'app/templates/kubernetes_operations/secrets/reveal.html',
    'app/templates/kubernetes_operations/secrets/tls_rotation.html',
)
ROUTE_FILES = (
    'app/kubernetes_operations/configmaps/routes.py',
    'app/kubernetes_operations/secrets/crud_routes.py',
    'app/kubernetes_operations/secrets/reveal_routes.py',
    'app/kubernetes_operations/secrets/tls_routes.py',
)
RELEASE_EVIDENCE = (
    'tests/contracts/kubernetes_operations/test_kubernetes_operations_final_release_contract.py',
    'tests/unit/kubernetes_operations/test_operation_flow.py',
    'tests/kubernetes_operations/test_route_authorization_characterization.py',
    'tests/integration/kubernetes_operations/test_live_runtime_boundary.py',
    'tests/security/kubernetes_operations/test_kubernetes_operations_security.py',
    'tests/rendering/kubernetes_operations/test_kubernetes_operations_rendering.py',
    'tests/e2e/kubernetes_operations/test_kubernetes_operations_smoke.py',
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

    root_routes = read('app/kubernetes_operations/routes.py')
    operation_flow = read('app/kubernetes_operations/operation_flow.py')
    shared_ui = read('app/templates/components/kubernetes_operation_ui.html')
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    pattern = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')
    configmap_readme = read('app/kubernetes_operations/configmaps/README.md')
    secret_readme = read('app/kubernetes_operations/secrets/README.md')

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
    for token in (
        'def cluster_required[',
        'has_registered_clusters()',
        "request.headers.get('HX-Request') == 'true'",
        "render_template('components/cluster/_onboarding_banner.html')",
    ):
        require(token in operation_flow, f'Operations cluster prerequisite is missing: {token}', errors)

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

    for relative in MUTATION_TEMPLATES:
        source = read(relative)
        if relative == 'app/templates/kubernetes_operations/configmaps/create.html':
            for token in (
                'data-kubernetes-operation-layout="context-rail-v4"',
                'data-kubernetes-operation-experience="task-focused-v4"',
                'components/context_rail.html',
                "context_rail.layout_classes('wide')",
                'context_rail.rail_classes()',
                'components/info_flow.html',
                'components/information_guide_card.html',
                'Create ConfigMap Flow',
                'Creation Guardrails',
            ):
                require(token in source, f'ConfigMap Create context-rail reference missing: {token}', errors)
            require(
                'workflow_control(' not in source,
                'ConfigMap Create must keep workflow guidance in the compact right rail instead of a full-width workflow block.',
                errors,
            )
            continue

        require(
            'data-kubernetes-operation-layout="full-width-v2"' in source,
            f'{relative} must retain its current reviewed mutation workspace until migrated individually.',
            errors,
        )
        require(
            'workflow_control(' in source,
            f'{relative} must use the shared workflow/guardrail control until its task-focused migration.',
            errors,
        )

    single_tls = read('app/templates/kubernetes_operations/secrets/tls_rotate.html')
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

    for obsolete in (
        'app/kubernetes_operations/secrets/routes.py',
        'app/templates/kubernetes_operations/_components.html',
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
        'Canonical Mutation Workspace — Task-Fit Layout v4' in pattern,
        'Operations design pattern must document the task-fit v4 layout policy.',
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
        'tests/kubernetes_operations' in quality_gate,
        'quality_gate.sh must run Kubernetes Operations functional characterization explicitly.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Kubernetes Operations final-lock passed: AuthZ-first cluster prerequisites, '
        'task-appropriate ConfigMap/Secret mutation workspaces, shared context-rail ownership, layered release evidence, '
        'and canonical shared workflow ownership are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
