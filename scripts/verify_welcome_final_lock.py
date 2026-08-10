#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HERO_DESCRIPTION = (
    'Operate and govern infrastructure with unified visibility, workflows, analytics, reporting, and administration.'
)
EXPECTED_GROUP_KEYS = ('visibility', 'operations', 'assurance', 'platform')
UNIVERSAL_TARGET = ('Settings', None, 'settings.account')
FORBIDDEN_WELCOME_IMPORT_FRAGMENTS = (
    'app.alertmanager',
    'app.analytics',
    'app.cluster',
    'app.extensions',
    'app.integrations',
    'app.inventory',
    'app.kubernetes',
    'app.models',
    'app.prometheus',
    'sqlalchemy',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _literal_assignment(path: str, name: str) -> Any:
    tree = ast.parse(read(path), filename=path)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise ValueError(f'{path}: assignment {name} is missing or is not literal')


def _default_permissions() -> set[str]:
    definitions = _literal_assignment('app/rbac/defaults.py', 'DEFAULT_PERMISSIONS')
    return {str(item[0]) for item in definitions}


def _verify_route_contract(errors: list[str]) -> None:
    path = 'app/welcome/routes.py'
    source = read(path)
    tree = ast.parse(source, filename=path)
    index = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'index'),
        None,
    )
    require(index is not None, 'Welcome index route is missing.', errors)
    if index is None:
        return

    route_paths: set[str] = set()
    has_login_required = False
    for decorator in index.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == 'login_required':
            has_login_required = True
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == 'route'
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
        ):
            route_paths.add(decorator.args[0].value)

    require(route_paths == {'/', '/welcome'}, 'Welcome must own exactly / and /welcome.', errors)
    require(has_login_required, 'Welcome must remain authentication-protected with @login_required.', errors)
    require(
        "render_template(\n        'welcome/index.html'" in source,
        'Welcome route must render the canonical welcome/index.html template.',
        errors,
    )

    for fragment in FORBIDDEN_WELCOME_IMPORT_FRAGMENTS:
        require(fragment not in source, f'Welcome route must not import infrastructure/runtime dependency {fragment}.', errors)


def _verify_catalog_contract(errors: list[str]) -> None:
    path = 'app/welcome/shortcuts.py'
    source = read(path)
    try:
        group_definitions = _literal_assignment(path, 'WELCOME_WORKSPACE_GROUP_DEFINITIONS')
        shortcut_definitions = _literal_assignment(path, 'WELCOME_SHORTCUT_DEFINITIONS')
    except (SyntaxError, ValueError) as exc:
        errors.append(str(exc))
        return

    group_keys = tuple(str(item['key']) for item in group_definitions)
    require(group_keys == EXPECTED_GROUP_KEYS, 'Welcome capability group order or ownership changed.', errors)
    require(len(group_keys) == len(set(group_keys)), 'Welcome capability group keys must be unique.', errors)

    permission_catalog = _default_permissions()
    titles: list[str] = []
    universal_targets: list[tuple[str, str | None, str]] = []

    for definition in shortcut_definitions:
        title = str(definition.get('title') or '')
        titles.append(title)
        group = str(definition.get('group') or '')
        targets = definition.get('targets') or ()

        require(group in group_keys, f'{title}: Welcome shortcut references unknown group {group!r}.', errors)
        require(bool(targets), f'{title}: Welcome shortcut must declare at least one target.', errors)
        require(bool(definition.get('scope')), f'{title}: Welcome shortcut scope is required.', errors)
        require(bool(definition.get('label')), f'{title}: Welcome shortcut functional label is required.', errors)
        require(bool(definition.get('description')), f'{title}: Welcome shortcut description is required.', errors)

        for permission_key, endpoint in targets:
            require(bool(endpoint), f'{title}: Welcome shortcut endpoint must not be empty.', errors)
            if permission_key is None:
                universal_targets.append((title, permission_key, str(endpoint)))
                continue
            require(
                permission_key in permission_catalog,
                f'{title}: unknown permission key {permission_key!r} in Welcome catalog.',
                errors,
            )

    require(len(titles) == len(set(titles)), 'Welcome shortcut titles must be unique.', errors)
    require(
        universal_targets == [UNIVERSAL_TARGET],
        'Only Settings → settings.account may bypass a domain permission for authenticated users.',
        errors,
    )

    require(
        "current_user.has_permission(permission_key)" in source,
        'Welcome catalog must filter discoverability with current_user.has_permission().',
        errors,
    )
    require(
        'if not shortcuts:\n            continue' in source,
        'Welcome catalog must omit empty unauthorized capability groups.',
        errors,
    )
    for fragment in FORBIDDEN_WELCOME_IMPORT_FRAGMENTS:
        require(fragment not in source, f'Welcome catalog must not import infrastructure/runtime dependency {fragment}.', errors)

    governance = next((item for item in shortcut_definitions if item.get('title') == 'K8s Governance'), None)
    reports = next((item for item in shortcut_definitions if item.get('title') == 'Reports'), None)
    intelligence = next((item for item in shortcut_definitions if item.get('title') == 'Intelligence'), None)
    require(governance is not None and governance.get('scope') == 'Compute', 'K8s Governance scope must be Compute.', errors)
    require(reports is not None and reports.get('scope') == 'Cross-domain', 'Reports must retain Cross-domain scope.', errors)
    require(
        intelligence is not None and intelligence.get('scope') == 'Cross-domain',
        'Intelligence must retain Cross-domain scope while the domain remains available.',
        errors,
    )


def _verify_presentation_contract(errors: list[str]) -> None:
    template = read('app/templates/welcome/index.html')
    capability = read('app/templates/components/welcome_capability_group.html')
    card = read('app/templates/components/workspace_link_card.html')
    script = read('app/static/js/welcome.js')

    require('components/page_hero.html' in template, 'Welcome must use the shared page hero.', errors)
    require('components/welcome_capability_group.html' in template, 'Welcome must use shared capability groups.', errors)
    require('components/workspace_link_card.html' in template, 'Welcome must use shared workspace cards.', errors)
    require('components/states/_empty_state.html' in template, 'Welcome must use the shared empty state.', errors)
    require(
        EXPECTED_HERO_DESCRIPTION in ' '.join(template.split()),
        'Welcome hero description does not match the locked concise copy.',
        errors,
    )
    require('aria-live="polite"' in template, 'Welcome visible-result metadata must remain announced politely.', errors)
    require('<span class="sr-only">Search Available Workspaces</span>' in template, 'Welcome search must keep an accessible label.', errors)
    require('focus-visible:ring-2' in card, 'Welcome workspace cards must preserve visible keyboard focus.', errors)
    require('data-group-result-count' in capability, 'Welcome capability groups must expose filtered result counts.', errors)

    for forbidden in (' style=', ' onclick=', ' onchange=', ' onkeyup=', ' onkeydown='):
        require(forbidden not in template.lower(), f'Welcome page must not use page-local inline UI handler/style {forbidden.strip()}.', errors)

    for network_api in ('fetch(', 'XMLHttpRequest', 'axios.', 'htmx.ajax', 'WebSocket('):
        require(network_api not in script, f'Welcome search JS must remain client-only and must not call {network_api}.', errors)
    require("querySelectorAll('[data-workspace-card]')" in script, 'Welcome search must filter only rendered authorized cards.', errors)
    require('card.hidden = !matches' in script, 'Welcome search must hide unmatched rendered cards.', errors)
    require('group.hidden = visibleGroupCards.length === 0' in script, 'Welcome search must hide empty groups.', errors)
    require("event.key === '/'" in script and "event.key === 'Escape'" in script, 'Welcome search keyboard shortcuts changed.', errors)


def _verify_release_evidence(errors: list[str]) -> None:
    functional_test = ROOT / 'tests/welcome/test_welcome_characterization.py'
    require(functional_test.exists(), 'Welcome permanent behavioral characterization test is missing.', errors)
    if functional_test.exists():
        tree = ast.parse(functional_test.read_text(encoding='utf-8'), filename=str(functional_test))
        tests = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        require(len(tests) >= 4, 'Welcome requires at least four permanent behavior tests.', errors)

    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    core_lock = read('scripts/verify_core_kubernetes_final_lock.py')
    require('python scripts/verify_welcome_final_lock.py' in quality_gate, 'quality_gate.sh must run Welcome final-lock verification directly.', errors)
    require(
        "'tests/welcome/test_welcome_characterization.py': 4" in coverage,
        'Feature characterization coverage must require Welcome behavior evidence.',
        errors,
    )
    require(
        'verify_welcome_final_lock.py' in core_lock,
        'Core Kubernetes final lock must require Welcome verifier wiring.',
        errors,
    )

    readme = read('app/welcome/README.md')
    pattern = read('docs/design/patterns/WELCOME_WORKSPACE_CATALOG.md')
    require('Release evidence' in readme, 'Welcome README must document release evidence.', errors)
    require('Accessibility and keyboard contract' in pattern, 'Welcome pattern must document accessibility/keyboard behavior.', errors)
    require('Security boundary' in pattern, 'Welcome pattern must document the discoverability security boundary.', errors)


def main() -> int:
    errors: list[str] = []
    _verify_route_contract(errors)
    _verify_catalog_contract(errors)
    _verify_presentation_contract(errors)
    _verify_release_evidence(errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Welcome final-lock v2 passed: authenticated landing routes, role-aware discoverability, '
        'provider-free data boundaries, canonical Violet components, accessibility, behavioral coverage, '
        'and release-gate wiring are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
