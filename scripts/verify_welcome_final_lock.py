#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HERO_DESCRIPTION = 'Operate infrastructure through unified visibility, governance, automation, and reporting.'
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
        'Welcome hero description does not match the locked concise copy.',
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
    required_tests = {
        'tests/unit/welcome/test_welcome_target_resolution.py': 3,
        'tests/welcome/test_welcome_characterization.py': 4,
        'tests/security/welcome/test_welcome_security.py': 3,
        'tests/rendering/welcome/test_welcome_rendering.py': 2,
        'tests/e2e/welcome/test_welcome_smoke.py': 2,
        'tests/migrations/test_retire_welcome_view_permission.py': 2,
    }
    for relative, minimum in required_tests.items():
        require(
            _test_count(relative, errors) >= minimum,
            f'{relative}: Welcome requires at least {minimum} permanent tests.',
            errors,
        )

    e2e_smoke = read('tests/e2e/welcome/test_welcome_smoke.py')
    require(
        'from app.extensions.db import db' not in e2e_smoke and 'from app.models.user import User' not in e2e_smoke,
        'Welcome E2E smoke must remain dependency-isolated instead of requiring a live PostgreSQL database.',
        errors,
    )
    require(
        "monkeypatch.setattr(login_manager, '_user_callback'" in e2e_smoke,
        'Welcome E2E smoke must exercise authenticated Flask-Login rendering without a persistence dependency.',
        errors,
    )

    migration = read('migrations/versions/20260810_retire_welcome_view.py')
    require(
        "revision = '20260810_retire_welcome_view'" in migration
        and "down_revision = '20260809_auth_session_generation'" in migration,
        'Welcome permission-retirement migration must remain on the canonical Alembic head.',
        errors,
    )
    require(
        "RETIRED_PERMISSION_KEY = 'welcome.view'" in migration,
        'Welcome permission-retirement migration must explicitly own the retired key.',
        errors,
    )

    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    core_lock = read('scripts/verify_core_kubernetes_final_lock.py')
    require(
        'python scripts/verify_welcome_final_lock.py' in quality_gate,
        'quality_gate.sh must run Welcome final-lock verification directly.',
        errors,
    )
    require(
        'pytest -q tests/e2e -m e2e' in quality_gate,
        'quality_gate.sh must execute the explicit E2E smoke layer.',
        errors,
    )
    for relative, minimum in (
        ('tests/unit/welcome/test_welcome_target_resolution.py', 3),
        ('tests/welcome/test_welcome_characterization.py', 4),
        ('tests/security/welcome/test_welcome_security.py', 3),
        ('tests/rendering/welcome/test_welcome_rendering.py', 2),
        ('tests/e2e/welcome/test_welcome_smoke.py', 2),
    ):
        require(
            f"'{relative}': {minimum}" in coverage,
            f'Feature coverage must require {relative}.',
            errors,
        )
    require(
        'verify_welcome_final_lock.py' in core_lock,
        'Core Kubernetes final lock must require Welcome verifier wiring.',
        errors,
    )

    readme = read('app/welcome/README.md')
    pattern = read('docs/design/patterns/WELCOME_WORKSPACE_CATALOG.md')
    standard = read('docs/standards/KAORI_ENGINEERING_STANDARD_V1.md')
    rbac_review = read('docs/rbac/PERMISSION_REGISTRY_REVIEW.md')
    require('## Test strategy' in readme, 'Welcome README must document the layered test strategy.', errors)
    require('Release evidence' in readme, 'Welcome README must document release evidence.', errors)
    require(
        'Accessibility and keyboard contract' in pattern,
        'Welcome pattern must document accessibility/keyboard behavior.',
        errors,
    )
    require(
        'Security boundary' in pattern,
        'Welcome pattern must document the discoverability security boundary.',
        errors,
    )
    require(
        '## 25. Per-page final recheck checklist' in standard,
        'Engineering Standard must include the expanded release-review checklist.',
        errors,
    )
    require(
        '`welcome.view` is no longer part of the registry' in rbac_review,
        'RBAC documentation must record retirement of the false Welcome permission boundary.',
        errors,
    )


def main() -> int:
    sections = (
        (
            'Routing & Access',
            _verify_route_contract,
            'Locked Welcome routing and authentication requirements are not satisfied.',
            'app/welcome/routes.py',
        ),
        (
            'Role-Aware Discoverability',
            _verify_catalog_contract,
            'Locked Welcome catalog, permission, or discoverability requirements are not satisfied.',
            'app/welcome/shortcuts.py and app/definitions/catalogs/access/rbac/access.yaml',
        ),
        (
            'KAORI UI Standard',
            _verify_presentation_contract,
            'Locked Welcome presentation, accessibility, or client-only search requirements are not satisfied.',
            'app/templates/welcome/index.html, shared Welcome components, and app/static/js/welcome.js',
        ),
        (
            'Release Evidence',
            _verify_release_evidence,
            'Locked Welcome test, migration, documentation, or release-gate evidence is not satisfied.',
            'Welcome tests, migration, quality gate, coverage verifier, and governance documentation',
        ),
    )

    results: list[tuple[str, list[str], str, str]] = []
    for name, verifier, why, where in sections:
        errors: list[str] = []
        verifier(errors)
        results.append((name, errors, why, where))

    failed = sum(bool(errors) for _, errors, _, _ in results)
    passed = len(results) - failed
    print(f'{"FAIL" if failed else "PASS"} — KAORI Welcome Final Lock')

    for name, errors, why, where in results:
        print()
        print(f'{name} — {"FAIL" if errors else "PASS"}')
        if not errors:
            continue
        for error in errors:
            print(f'  WHAT — {error}')
        print(f'  WHY — {why}')
        print(f'  WHERE — {where}')

    print()
    print(f'Summary — {passed} passed · {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())