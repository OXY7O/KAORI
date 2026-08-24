#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_PROVIDER_DOMAIN_BOUNDARIES = (
    (
        'metrics_source',
        Path('integrations/observability/metrics_source'),
        'app.integrations.observability.metrics_source.application',
    ),
    (
        'alertmanager',
        Path('integrations/observability/alert_source/providers/alertmanager'),
        'app.integrations.observability.alert_source.providers.alertmanager.application',
    ),
    (
        'minio',
        Path('integrations/storage/object_storage/providers/minio'),
        'app.integrations.storage.object_storage.providers.minio.application',
    ),
)

_RETIRED_PYTHON_MODULES = {
    'app.kubernetes.analytics.alerts.queries',
    'app.kubernetes.analytics.alerts.service',
    'app.kubernetes.analytics.capacity.helpers',
    'app.kubernetes.analytics.capacity.queries',
    'app.kubernetes.analytics.common.dependencies',
    'app.kubernetes.analytics.forecast.queries',
    'app.kubernetes.analytics.overview.queries',
    'app.kubernetes.analytics.storage.queries',
    'app.kubernetes.analytics.top_consumers.queries',
    'app.kubernetes.analytics.utilization.queries',
    'app.kubernetes.analytics.workload.queries',
    'app.integrations.observability.alert_source.providers.alertmanager.alerts',
    'app.integrations.observability.alert_source.providers.alertmanager.schemas',
    'app.integrations.observability.alert_source.providers.alertmanager.silences',
    'app.integrations.deprecations',
    'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.actions',
    'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.discovery',
    'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.inventory',
    'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.schemas',
    'app.integrations.observability.metrics_source.evidence',
    'app.integrations.observability.metrics_source.queries',
    'app.integrations.observability.metrics_source.schemas',
    'app.integrations.observability.metrics_source.validation',
    'app.integrations.runtime.contracts',
    'app.integrations.runtime.dispatcher',
    'app.integrations.runtime.service',
    'app.platform_operations.jobs.query_execution',
    'app.platform_operations.jobs.query_planning',
    'app.platform_operations.jobs.resource_limits',
    'app.kubernetes.inventory.collector',
    'app.kubernetes.inventory.service',
    'app.integrations.observability.metrics_source.application.binding_contract',
    'app.reports.storage.base',
    'app.access.users.lifecycle',
    'app.utils.formatters',
    'app.utils.helpers',
}


@dataclass(frozen=True)
class ImportRecord:
    source: Path
    line: int
    target: str
    imported_names: tuple[str, ...] = ()
    wildcard: bool = False


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root.parent).with_suffix('')
    parts = list(relative.parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def scan_imports(app_root: Path) -> list[ImportRecord]:
    records: list[ImportRecord] = []
    for path in sorted(app_root.rglob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:
            raise ValueError(f'{path}:{exc.lineno}: cannot parse source: {exc.msg}') from exc

        current_module = _module_name(app_root, path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    records.append(
                        ImportRecord(
                            source=path,
                            line=node.lineno,
                            target=alias.name,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                target = node.module or ''
                if node.level:
                    current_parts = current_module.split('.')
                    package_parts = current_parts if path.name == '__init__.py' else current_parts[:-1]
                    base_parts = package_parts[: max(len(package_parts) - node.level + 1, 0)]
                    target = '.'.join([*base_parts, target] if target else base_parts)
                names = tuple(alias.name for alias in node.names)
                records.append(
                    ImportRecord(
                        source=path,
                        line=node.lineno,
                        target=target,
                        imported_names=names,
                        wildcard='*' in names,
                    )
                )
    return records


def _logical_domain(module: str) -> str | None:
    """Map physical packages to stable architecture domains used by debt baselines.

    Physical package consolidation must not turn pre-existing logical boundaries into one
    giant graph node. The mapping deliberately preserves the prior bounded-context names
    while allowing their code to live under clearer domain-first folders.
    """
    if module == 'app':
        return '__root__'
    if not module.startswith('app.'):
        return None

    prefix_domains = (
        ('app.access.authentication', 'auth'),
        ('app.access.rbac', 'rbac'),
        ('app.access.users', 'users'),
        ('app.access.identity_providers', 'identity_providers'),
        ('app.platform_operations.notifications.alert_delivery', 'alert_delivery'),
        ('app.platform_operations.notifications', 'notifications'),
        ('app.platform_operations.jobs', 'jobs'),
        ('app.platform_operations.data_lifecycle.retention', 'retention'),
        ('app.integrations.delivery.notification_channels', 'notification_channels'),
        ('app.integrations.observability.metrics_source.application', 'metrics_sources'),
        ('app.integrations.observability.alert_source.providers.alertmanager.application', 'alert_sources'),
        ('app.integrations.storage.object_storage.providers.minio.application', 'object_storage'),
        ('app.kubernetes.cluster', 'cluster'),
        ('app.kubernetes.inventory', 'inventory'),
        ('app.kubernetes.analytics', 'analytics'),
        ('app.storage.object_storage.analytics', 'analytics'),
        ('app.storage.object_storage.inventory', 'inventory'),
        ('app.kubernetes.dashboard', 'dashboards'),
        ('app.kubernetes.governance', 'governance'),
        ('app.kubernetes.operations', 'kubernetes_operations'),
        ('app.intelligence.alert_intelligence', 'alert_intelligence'),
        ('app.intelligence.recommendation_alert_commands', 'alert_intelligence'),
        ('app.intelligence.automation_control', 'automation_control'),
        ('app.intelligence.knowledge', 'knowledge'),
        ('app.intelligence.resolver', 'resolver'),
    )
    for prefix, domain in prefix_domains:
        if module == prefix or module.startswith(f'{prefix}.'):
            return domain

    parts = module.split('.')
    return parts[1] if len(parts) > 1 else '__root__'


def _source_domain(app_root: Path, source: Path) -> str:
    return _logical_domain(_module_name(app_root, source)) or '__root__'


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[set[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph.get(node, ())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] == indices[node]:
            component: set[str] = set()
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.add(member)
                if member == node:
                    break
            components.append(component)

    nodes = set(graph)
    for targets in graph.values():
        nodes.update(targets)
    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return components


def validate_boundaries(
    app_root: Path,
    records: Iterable[ImportRecord],
    baseline: dict[str, object],
) -> list[str]:
    records = list(records)
    errors: list[str] = []

    retired_paths = tuple(
        app_root.parent / Path(*module.split('.')).with_suffix('.py') for module in sorted(_RETIRED_PYTHON_MODULES)
    ) + (
        app_root / 'static' / 'js' / 'dashboard.js',
        app_root / 'static' / 'js' / 'report.js',
    )
    for path in retired_paths:
        if path.exists():
            errors.append(f'retired compatibility or empty artifact still exists: {path}')

    service_form_imports: set[tuple[str, str]] = set()
    graph: dict[str, set[str]] = {}

    for record in records:
        relative_source = record.source.relative_to(app_root.parent).as_posix()
        if record.wildcard:
            errors.append(f'{relative_source}:{record.line}: wildcard import from {record.target!r} is forbidden')

        if record.target in _RETIRED_PYTHON_MODULES:
            errors.append(f'{relative_source}:{record.line}: import targets retired module {record.target!r}')

        relative_to_app = record.source.relative_to(app_root)
        for provider, kernel_root, forbidden_domain in _PROVIDER_DOMAIN_BOUNDARIES:
            if not relative_to_app.is_relative_to(kernel_root):
                continue
            application_root = kernel_root / 'application'
            if relative_to_app.is_relative_to(application_root):
                continue
            if record.target == forbidden_domain or record.target.startswith(f'{forbidden_domain}.'):
                errors.append(
                    f'{relative_source}:{record.line}: canonical {provider.replace("_", " ").title()} kernel '
                    f'may not import its web/application workspace ({record.target})'
                )

        if record.source == app_root / 'integrations' / 'binding_service.py':
            forbidden_binding_import = any(
                record.target == domain or record.target.startswith(f'{domain}.')
                for _, _, domain in _PROVIDER_DOMAIN_BOUNDARIES
            )
            if forbidden_binding_import:
                errors.append(
                    f'{relative_source}:{record.line}: provider-neutral binding orchestration may not '
                    f'import provider web/domain modules ({record.target})'
                )

        target_parts = record.target.split('.')
        imports_routes = 'routes' in target_parts
        imports_forms = 'forms' in target_parts
        source_domain = _source_domain(app_root, record.source)
        target_domain = _logical_domain(record.target)
        source_is_bootstrap = (
            record.source
            in {
                app_root / '__init__.py',
                app_root / 'bootstrap' / 'blueprints.py',
            }
            or record.source.name == '__init__.py'
        )
        source_is_domain_router = record.source.name == 'routes.py' and target_domain == source_domain

        if imports_routes and not (source_is_bootstrap or source_is_domain_router):
            errors.append(
                f'{relative_source}:{record.line}: only bootstrap or same-domain router modules may import routes ({record.target})'
            )

        if record.source.is_relative_to(app_root / 'models'):
            forbidden_flask_names = {'request', 'current_app', 'session', 'g'}
            if record.target == 'flask' and forbidden_flask_names.intersection(record.imported_names):
                errors.append(f'{relative_source}:{record.line}: models may not depend on Flask request globals')
            if record.target == 'flask_login' and 'current_user' in record.imported_names:
                errors.append(f'{relative_source}:{record.line}: models may not depend on current_user')
            if imports_routes or imports_forms:
                errors.append(
                    f'{relative_source}:{record.line}: models may not import web routes/forms ({record.target})'
                )

        if record.source.name == 'tasks.py' or record.source.name.endswith('_tasks.py'):
            if imports_routes or imports_forms:
                errors.append(
                    f'{relative_source}:{record.line}: task modules may not import web routes/forms ({record.target})'
                )

        is_service = record.source.name in {'service.py', 'services.py'} or record.source.name.endswith('_service.py')
        if is_service and imports_routes:
            errors.append(f'{relative_source}:{record.line}: service modules may not import routes ({record.target})')
        if is_service and imports_forms:
            service_form_imports.add((relative_source, record.target))

        if target_domain is not None and target_domain != source_domain:
            graph.setdefault(source_domain, set()).add(target_domain)

    allowed_service_form_imports = {
        (str(item['source']), str(item['target']))
        for item in baseline.get('service_form_imports', [])
        if isinstance(item, dict) and 'source' in item and 'target' in item
    }
    new_form_edges = sorted(service_form_imports - allowed_service_form_imports)
    stale_form_edges = sorted(allowed_service_form_imports - service_form_imports)
    for source, target in new_form_edges:
        errors.append(f'new service-to-form dependency is forbidden: {source} -> {target}')
    for source, target in stale_form_edges:
        errors.append(
            f'architecture debt baseline is stale; remove resolved service-to-form edge: {source} -> {target}'
        )

    envelopes = [set(item.get('domains', [])) for item in baseline.get('cycle_envelopes', []) if isinstance(item, dict)]
    for component in _strongly_connected_components(graph):
        if len(component) < 2:
            continue
        if not any(component <= envelope for envelope in envelopes):
            errors.append('new or expanded top-level dependency cycle: ' + ', '.join(sorted(component)))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate KAORI Python dependency boundaries.')
    parser.add_argument('--app-root', type=Path, default=Path('app'))
    parser.add_argument(
        '--baseline',
        type=Path,
        default=Path('docs/architecture/architecture-debt-baseline.json'),
    )
    args = parser.parse_args()

    try:
        baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
        records = scan_imports(args.app_root)
        errors = validate_boundaries(args.app_root, records, baseline)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}')
        return 1

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(f'KAORI architecture boundaries are valid across {len(records)} imports.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
