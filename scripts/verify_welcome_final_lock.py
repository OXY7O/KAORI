#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HERO_DESCRIPTION = (
    'Operate infrastructure through unified visibility, governance, automation, reporting, and role-aware operational workspaces.'
)
EXPECTED_GROUP_KEYS = ('visibility', 'operations', 'assurance', 'platform')
UNIVERSAL_TARGET = ('Settings', None, 'settings.account')
FORBIDDEN_WELCOME_IMPORT_FRAGMENTS = (
    'app.integrations.observability.alert_source.providers.alertmanager.application',
    'app.analytics',
    'app.kubernetes.cluster',
    'app.extensions',
    'app.integrations',
    'app.inventory',
    'app.kubernetes',
    'app.models',
    'app.integrations.observability.metrics_source.application',
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
    document = yaml.safe_load(read('app/definitions/catalogs/access/rbac/access.yaml'))
    return {str(item['key']) for item in document['permissions']}


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
        require(
            fragment not in source,
            f'Welcome route must not import infrastructure/runtime dependency {fragment}.',
            errors,
        )


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
    require(
        'welcome.view' not in permission_catalog,
        'welcome.view is a retired non-enforcing permission and must not return to the registry.',
        errors,
    )
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
        'current_user.has_permission' in source and 'resolve_welcome_target(' in source,
        'Welcome catalog must resolve discoverability through the canonical permission-aware target resolver.',
        errors,
    )
    require(
        'if not shortcuts:\n            continue' in source,
        'Welcome catalog must omit empty unauthorized capability groups.',
        errors,
    )
    for fragment in FORBIDDEN_WELCOME_IMPORT_FRAGMENTS:
        require(
            fragment not in source,
            f'Welcome catalog must not import infrastructure/runtime dependency {fragment}.',
            errors,
        )

    governance = next((item for item in shortcut_definitions if item.get('title') == 'Kubernetes Governance'), None)
    reports = next((item for item in shortcut_definitions if item.get('title') == 'Reports'), None)
    intelligence = next((item for item in shortcut_definitions if item.get('title') == 'Intelligence'), None)
    require(
        governance is not None and governance.get('scope') == 'Compute',
        'Kubernetes Governance scope must be Compute.',
        errors,
    )
    require(
        reports is not None and reports.get('scope') == 'Cross-domain',
        'Reports must retain Cross-domain scope.',
        errors,
    )
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
    require(
        "page_hero.context_header('Access Scope', 'Role-Aware Workspace', 'key-round')" in template,
        'Welcome Hero right header must use the canonical Context Icon Box variant.',
        errors,
    )
    require(
        'components/welcome_capability_group.html' in template, 'Welcome must use shared capability groups.', errors
    )
    require('components/workspace_link_card.html' in template, 'Welcome must use shared workspace cards.', errors)
    require('components/states/_empty_state.html' in template, 'Welcome must use the shared empty state.', errors)
    require(
        EXPECTED_HERO_DESCRIPTION in ' '.join(template.split()),
        'Welcome hero description does not match the locked Hero v1.7 copy.',
        errors,
    )
    require('aria-live="polite"' in template, 'Welcome visible-result metadata must remain announced politely.', errors)
    require(
        '<span class="sr-only">Search Available Workspaces</span>' in template,
        'Welcome search must keep an accessible label.',
        errors,
    )
    require('focus-visible:ring-2' in card, 'Welcome workspace cards must preserve visible keyboard focus.', errors)
    require(
        'data-group-result-count' in capability, 'Welcome capability groups must expose filtered result counts.', errors
    )

    for forbidden in (' style=', ' onclick=', ' onchange=', ' onkeyup=', ' onkeydown='):
        require(
            forbidden not in template.lower(),
            f'Welcome page must not use page-local inline UI handler/style {forbidden.strip()}.',
            errors,
        )

    for network_api in ('fetch(', 'XMLHttpRequest', 'axios.', 'htmx.ajax', 'WebSocket('):
        require(
            network_api not in script,
            f'Welcome search JS must remain client-only and must not call {network_api}.',
            errors,
        )
    require(
        "querySelectorAll('[data-workspace-card]')" in script,
        'Welcome search must filter only rendered authorized cards.',
        errors,
    )
    require('card.hidden = !matches' in script, 'Welcome search must hide unmatched rendered cards.', errors)
    require('group.hidden = visibleGroupCards.length === 0' in script, 'Welcome search must hide empty groups.', errors)
    require(
        "event.key === '/'" in script and "event.key === 'Escape'" in script,
        'Welcome search keyboard shortcuts changed.',
        errors,
    )


def _test_count(relative: str, errors: list[str]) -> int:
    path = ROOT / relative
    require(path.exists(), f'{relative}: required Welcome release-test module is missing.', errors)
    if not path.exists():
        return 0
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError as exc:
        errors.append(f'{relative}:{exc.lineno}: invalid Python test module')
        return 0
    return sum(
        1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
    )


def _verify_release_evidence(errors: list[str]) -> None:
    required_tests = (
        'tests/contracts/release/test_welcome_final_lock_contract.py',
        'tests/contracts/release/test_welcome_governance_contract.py',
    )
    total_tests = sum(_test_count(relative, errors) for relative in required_tests)
    require(total_tests >= 10, 'Welcome release evidence must retain at least 10 focused contract tests.', errors)


def verify() -> None:
    sections: list[tuple[str, list[str]]] = []
    for label, verifier in (
        ('Routing & Access', _verify_route_contract),
        ('Role-Aware Discoverability', _verify_catalog_contract),
        ('KAORI UI Standard', _verify_presentation_contract),
        ('Release Evidence', _verify_release_evidence),
    ):
        errors: list[str] = []
        verifier(errors)
        sections.append((label, errors))

    failures = [(label, errors) for label, errors in sections if errors]
    print('PASS — KAORI Welcome Final Lock' if not failures else 'FAIL — KAORI Welcome Final Lock')
    for label, errors in sections:
        print(f'\n{label} — {"PASS" if not errors else "FAIL"}')
        for error in errors:
            print(f'  WHAT — {error}')
            print(
                '  WHY — Locked Welcome presentation, accessibility, or client-only search requirements are not satisfied.'
            )
            print('  WHERE — app/templates/welcome/index.html, shared Welcome components, and app/static/js/welcome.js')
    print(f'\nSummary — {len(sections) - len(failures)} passed · {len(failures)} failed')
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    verify()
