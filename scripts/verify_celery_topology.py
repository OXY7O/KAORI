#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

_AUTOMATION_QUEUE = 'automation'
_AUTOMATION_TASKS = frozenset(
    {
        'app.infrastructure_automation.tasks.collect_localhost_facts',
        'app.infrastructure_automation.tasks.materialize_kubespray_plan_review',
    }
)


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    name: str
    module: str
    function: str
    parameters: frozenset[str]


def _module_name(app_root: Path, path: Path) -> str:
    relative = path.relative_to(app_root.parent).with_suffix('')
    parts = list(relative.parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def discover_tasks(app_root: Path) -> dict[str, TaskDefinition]:
    tasks: dict[str, TaskDefinition] = {}
    for path in sorted(app_root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        module = _module_name(app_root, path)
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            task_name: str | None = None
            for decorator in node.decorator_list:
                call = decorator if isinstance(decorator, ast.Call) else None
                target = call.func if call is not None else decorator
                decorator_name = (
                    target.id
                    if isinstance(target, ast.Name)
                    else target.attr
                    if isinstance(target, ast.Attribute)
                    else ''
                )
                if decorator_name not in {'shared_task', 'task'}:
                    continue
                if call is not None:
                    for keyword in call.keywords:
                        if keyword.arg == 'name' and isinstance(keyword.value, ast.Constant):
                            task_name = str(keyword.value.value)
                            break
                task_name = task_name or f'{module}.{node.name}'
                break
            if task_name is None:
                continue
            parameters = {
                argument.arg
                for argument in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                )
            }
            tasks[task_name] = TaskDefinition(
                name=task_name,
                module=module,
                function=node.name,
                parameters=frozenset(parameters),
            )
    return tasks


def _resolve_string(node: ast.AST, values: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        for value in reversed(node.values):
            resolved = _resolve_string(value, values)
            if resolved is not None:
                return resolved
        return None
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id == '_retention_queue_name':
                return 'maintenance'
            if node.func.id in {'_env_str', '_env_optional_str'}:
                if len(node.args) >= 2:
                    return _resolve_string(node.args[1], values)
                return None
        if isinstance(node.func, ast.Attribute):
            return _resolve_string(node.func.value, values)
    return None


def parse_celery_config(config_path: Path) -> tuple[set[str], dict[str, str]]:
    tree = ast.parse(config_path.read_text(encoding='utf-8'), filename=str(config_path))
    config_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Config')
    values: dict[str, str] = {}
    celery_dict: ast.Dict | None = None
    for statement in config_class.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id == 'CELERY' and isinstance(statement.value, ast.Dict):
            celery_dict = statement.value
            continue
        resolved = _resolve_string(statement.value, values)
        if resolved is not None:
            values[target.id] = resolved
    if celery_dict is None:
        raise ValueError('Config.CELERY dictionary was not found.')

    payload = {
        str(key.value): value
        for key, value in zip(celery_dict.keys, celery_dict.values, strict=True)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    imports_node = payload.get('imports')
    routes_node = payload.get('task_routes')
    if not isinstance(imports_node, (ast.Tuple, ast.List)) or not isinstance(routes_node, ast.Dict):
        raise ValueError('Config.CELERY imports/task_routes must remain literal collections.')

    imports = {
        str(item.value) for item in imports_node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }
    routes: dict[str, str] = {}
    for key, route_value in zip(routes_node.keys, routes_node.values, strict=True):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            raise ValueError('Celery task route names must be string literals.')
        if not isinstance(route_value, ast.Dict):
            raise ValueError(f'Celery route for {key.value} must be a literal dictionary.')
        queue_expr = None
        for route_key, value in zip(route_value.keys, route_value.values, strict=True):
            if isinstance(route_key, ast.Constant) and route_key.value == 'queue':
                queue_expr = value
                break
        if queue_expr is None:
            raise ValueError(f'Celery route for {key.value} does not define a queue.')
        queue = _resolve_string(queue_expr, values)
        if not queue:
            raise ValueError(f'Celery route queue for {key.value} cannot be resolved statically.')
        routes[str(key.value)] = queue
    return imports, routes


def parse_worker_queues(compose_path: Path) -> set[str]:
    source = compose_path.read_text(encoding='utf-8')
    queues: set[str] = set()
    pattern = re.compile(r'--queues=(?:"\$\$\{[A-Z0-9_]+:-([^}]+)\}"|([^\s]+))')
    for match in pattern.finditer(source):
        queue = (match.group(1) or match.group(2) or '').strip('"\'')
        if queue:
            queues.update(item.strip() for item in queue.split(',') if item.strip())
    return queues


def discover_canonical_dispatch_targets(app_root: Path) -> set[str]:
    targets: set[str] = set()
    for path in sorted(app_root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        aliases: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f'{node.module}.{alias.name}'
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ''
            )
            if function_name != 'enqueue_canonical_job':
                continue
            task_keyword = next((item for item in node.keywords if item.arg == 'task'), None)
            if task_keyword is None or not isinstance(task_keyword.value, ast.Name):
                continue
            resolved = aliases.get(task_keyword.value.id)
            if resolved:
                targets.add(resolved)
    return targets


def validate_automation_pilot(
    *,
    routes: dict[str, str],
    dockerfile: str,
    config_source: str,
    default_compose_source: str,
    default_worker_queues: set[str],
) -> list[str]:
    """Prove the existing isolated, opt-in worker instead of activating it by default."""
    errors: list[str] = []
    automation_tasks = {name for name, queue in routes.items() if queue == _AUTOMATION_QUEUE}
    if automation_tasks != _AUTOMATION_TASKS:
        errors.append('Automation queue must route exactly the two approved Infrastructure Automation tasks.')
    if _AUTOMATION_QUEUE in default_worker_queues or 'automation-worker' in default_compose_source:
        errors.append('Automation pilot must not be consumed or started by the default Compose fleet.')
    if 'KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED' in default_compose_source:
        errors.append('Default Compose must not activate the localhost automation pilot.')

    stages = re.split(r'(?m)^FROM ', dockerfile)[1:]
    pilot_stages = [stage for stage in stages if stage.splitlines()[0] == 'base AS automation-worker']
    if len(pilot_stages) != 1:
        errors.append('Automation queue requires the dedicated base AS automation-worker Dockerfile target.')
    else:
        stage = pilot_stages[0]
        users = re.findall(r'(?m)^USER (.+)
    app_root = root / 'app'
    tasks = discover_tasks(app_root)
    config_path = app_root / 'config' / 'default.py'
    imports, routes = parse_celery_config(config_path)
    production_compose = root / 'compose.production.yml'
    worker_queues = parse_worker_queues(production_compose)
    development_compose = root / '.devcontainer' / 'compose.devcontainer.yml'
    development_worker_queues = parse_worker_queues(development_compose)
    production_source = production_compose.read_text(encoding='utf-8')
    development_source = development_compose.read_text(encoding='utf-8')
    errors = validate_automation_pilot(
        routes=routes,
        dockerfile=(root / 'Dockerfile').read_text(encoding='utf-8'),
        config_source=config_path.read_text(encoding='utf-8'),
        default_compose_source=production_source + '\n' + development_source,
        default_worker_queues=worker_queues | development_worker_queues,
    )

    task_modules = {task.module for task in tasks.values()}
    for module in sorted(task_modules - imports):
        errors.append(f'Celery task module is not imported at worker startup: {module}')
    for module in sorted(imports - task_modules):
        errors.append(f'Celery imports contains a module without tasks: {module}')

    for name in sorted(set(tasks) - set(routes)):
        errors.append(f'Celery task has no explicit route: {name}')
    for name in sorted(set(routes) - set(tasks)):
        errors.append(f'Celery route targets an unknown task: {name}')

    # The separately validated pilot consumer is not part of either default fleet.
    route_queues = set(routes.values()) - {_AUTOMATION_QUEUE}
    for queue in sorted(route_queues - worker_queues):
        errors.append(f'Celery routed queue has no production worker: {queue}')
    for queue in sorted(worker_queues - route_queues):
        errors.append(f'Production worker consumes a queue with no registered task route: {queue}')

    for queue in sorted(route_queues - development_worker_queues):
        errors.append(f'Celery routed queue has no Dev Container worker: {queue}')
    for queue in sorted(development_worker_queues - route_queues):
        errors.append(f'Dev Container worker consumes a queue with no registered task route: {queue}')

    canonical_development_services = {
        'inventory-worker',
        'registry-security-worker',
        'maintenance-worker',
        'runtime-worker',
        'validation-worker',
        'analytics-worker',
        'reports-worker',
        'forecasting-worker',
        'resolver-execution-worker',
        'resolver-maintenance-worker',
        'beat',
    }
    for service in sorted(canonical_development_services):
        if f'  {service}:\n' not in development_source:
            errors.append(f'Dev Container compose does not define {service}.')
    if '--hostname=reports@%h' not in development_source:
        errors.append('Dev Container reports-worker has no canonical reports hostname.')

    if '--hostname=registry-security@%h' not in development_source:
        errors.append('Dev Container registry-security-worker has no canonical registry-security hostname.')

    if '--hostname=reports@%h' not in production_source:
        errors.append('Production reports-worker has no canonical reports hostname.')

    if '--hostname=registry-security@%h' not in production_source:
        errors.append('Production registry-security-worker has no canonical registry-security hostname.')

    devcontainer_config = json.loads((root / '.devcontainer' / 'devcontainer.json').read_text(encoding='utf-8'))
    run_services = set(devcontainer_config.get('runServices') or [])
    if 'automation-worker' in run_services:
        errors.append('Dev Container runServices must not start the opt-in automation worker.')
    for service in sorted(canonical_development_services):
        if service not in run_services:
            errors.append(f'Dev Container runServices does not start {service}.')

    definitions_by_symbol = {f'{task.module}.{task.function}': task for task in tasks.values()}
    for symbol in sorted(discover_canonical_dispatch_targets(app_root)):
        task = definitions_by_symbol.get(symbol)
        if task is None:
            errors.append(f'Canonical dispatcher targets an unknown task symbol: {symbol}')
        elif 'job_execution_id' not in task.parameters:
            errors.append(f'Canonical dispatcher task does not accept injected job_execution_id: {symbol}')
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        errors = validate(root)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f'ERROR: {exc}')
        return 1
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    tasks = discover_tasks(root / 'app')
    _, routes = parse_celery_config(root / 'app' / 'config' / 'default.py')
    queues = parse_worker_queues(root / 'compose.production.yml')
    print(
        f'KAORI Celery topology is closed: {len(tasks)} tasks, '
        f'{len(routes)} explicit routes, {len(queues)} default consumed queues, 1 isolated opt-in queue.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
, stage)
        commands = re.findall(r'(?m)^CMD (.+)
    app_root = root / 'app'
    tasks = discover_tasks(app_root)
    imports, routes = parse_celery_config(app_root / 'config' / 'default.py')
    worker_queues = parse_worker_queues(root / 'compose.production.yml')
    development_compose = root / '.devcontainer' / 'compose.devcontainer.yml'
    development_worker_queues = parse_worker_queues(development_compose)
    errors: list[str] = []

    task_modules = {task.module for task in tasks.values()}
    for module in sorted(task_modules - imports):
        errors.append(f'Celery task module is not imported at worker startup: {module}')
    for module in sorted(imports - task_modules):
        errors.append(f'Celery imports contains a module without tasks: {module}')

    for name in sorted(set(tasks) - set(routes)):
        errors.append(f'Celery task has no explicit route: {name}')
    for name in sorted(set(routes) - set(tasks)):
        errors.append(f'Celery route targets an unknown task: {name}')

    route_queues = set(routes.values())
    for queue in sorted(route_queues - worker_queues):
        errors.append(f'Celery routed queue has no production worker: {queue}')
    for queue in sorted(worker_queues - route_queues):
        errors.append(f'Production worker consumes a queue with no registered task route: {queue}')

    for queue in sorted(route_queues - development_worker_queues):
        errors.append(f'Celery routed queue has no Dev Container worker: {queue}')
    for queue in sorted(development_worker_queues - route_queues):
        errors.append(f'Dev Container worker consumes a queue with no registered task route: {queue}')

    development_source = development_compose.read_text(encoding='utf-8')
    canonical_development_services = {
        'inventory-worker',
        'registry-security-worker',
        'maintenance-worker',
        'runtime-worker',
        'validation-worker',
        'analytics-worker',
        'reports-worker',
        'forecasting-worker',
        'resolver-execution-worker',
        'resolver-maintenance-worker',
        'beat',
    }
    for service in sorted(canonical_development_services):
        if f'  {service}:\n' not in development_source:
            errors.append(f'Dev Container compose does not define {service}.')
    if '--hostname=reports@%h' not in development_source:
        errors.append('Dev Container reports-worker has no canonical reports hostname.')

    if '--hostname=registry-security@%h' not in development_source:
        errors.append('Dev Container registry-security-worker has no canonical registry-security hostname.')

    production_source = (root / 'compose.production.yml').read_text(encoding='utf-8')
    if '--hostname=reports@%h' not in production_source:
        errors.append('Production reports-worker has no canonical reports hostname.')

    if '--hostname=registry-security@%h' not in production_source:
        errors.append('Production registry-security-worker has no canonical registry-security hostname.')

    devcontainer_config = json.loads((root / '.devcontainer' / 'devcontainer.json').read_text(encoding='utf-8'))
    run_services = set(devcontainer_config.get('runServices') or [])
    for service in sorted(canonical_development_services):
        if service not in run_services:
            errors.append(f'Dev Container runServices does not start {service}.')

    definitions_by_symbol = {f'{task.module}.{task.function}': task for task in tasks.values()}
    for symbol in sorted(discover_canonical_dispatch_targets(app_root)):
        task = definitions_by_symbol.get(symbol)
        if task is None:
            errors.append(f'Canonical dispatcher targets an unknown task symbol: {symbol}')
        elif 'job_execution_id' not in task.parameters:
            errors.append(f'Canonical dispatcher task does not accept injected job_execution_id: {symbol}')
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        errors = validate(root)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f'ERROR: {exc}')
        return 1
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    tasks = discover_tasks(root / 'app')
    _, routes = parse_celery_config(root / 'app' / 'config' / 'default.py')
    queues = parse_worker_queues(root / 'compose.production.yml')
    print(
        f'KAORI Celery topology is closed: {len(tasks)} tasks, '
        f'{len(routes)} explicit routes, {len(queues)} consumed queues.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
, stage)
        expected_command = [
            'celery',
            '--app',
            'celery_worker:celery_app',
            'worker',
            '--queues=automation',
            '--loglevel=INFO',
            '--concurrency=1',
            '--prefetch-multiplier=1',
            '--hostname=automation@%h',
        ]
        try:
            command = json.loads(commands[0]) if len(commands) == 1 else None
        except json.JSONDecodeError:
            command = None
        if users != ['kaori'] or command != expected_command:
            errors.append('Automation worker must run unprivileged with the exact isolated queue and bounded command.')
        if 'COPY requirements/automation-worker.txt /tmp/requirements/automation-worker.txt' not in stage:
            errors.append('Automation worker requires its isolated pinned dependency manifest.')

    if not stages or stages[-1].splitlines()[0] != 'base AS production':
        errors.append('Production must remain the final independent default Dockerfile target.')
    if re.search(r'(?im)^(?:FROM automation-worker\b|COPY .*--from=automation-worker\b)', dockerfile):
        errors.append('No other Dockerfile target may inherit or copy from the opt-in automation worker.')
    if 'requirements/automation-worker.txt' in ''.join(stage for stage in stages if stage not in pilot_stages):
        errors.append('Automation worker dependencies must remain outside default image stages.')

    config_tree = ast.parse(config_source)
    for node in ast.walk(config_tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == 'task'
                and isinstance(value, ast.Constant)
                and value.value in _AUTOMATION_TASKS
            ):
                errors.append(f'Opt-in automation task must not be scheduled by Beat: {value.value}')
    return errors


def validate(root: Path) -> list[str]:
    app_root = root / 'app'
    tasks = discover_tasks(app_root)
    imports, routes = parse_celery_config(app_root / 'config' / 'default.py')
    worker_queues = parse_worker_queues(root / 'compose.production.yml')
    development_compose = root / '.devcontainer' / 'compose.devcontainer.yml'
    development_worker_queues = parse_worker_queues(development_compose)
    errors: list[str] = []

    task_modules = {task.module for task in tasks.values()}
    for module in sorted(task_modules - imports):
        errors.append(f'Celery task module is not imported at worker startup: {module}')
    for module in sorted(imports - task_modules):
        errors.append(f'Celery imports contains a module without tasks: {module}')

    for name in sorted(set(tasks) - set(routes)):
        errors.append(f'Celery task has no explicit route: {name}')
    for name in sorted(set(routes) - set(tasks)):
        errors.append(f'Celery route targets an unknown task: {name}')

    route_queues = set(routes.values())
    for queue in sorted(route_queues - worker_queues):
        errors.append(f'Celery routed queue has no production worker: {queue}')
    for queue in sorted(worker_queues - route_queues):
        errors.append(f'Production worker consumes a queue with no registered task route: {queue}')

    for queue in sorted(route_queues - development_worker_queues):
        errors.append(f'Celery routed queue has no Dev Container worker: {queue}')
    for queue in sorted(development_worker_queues - route_queues):
        errors.append(f'Dev Container worker consumes a queue with no registered task route: {queue}')

    development_source = development_compose.read_text(encoding='utf-8')
    canonical_development_services = {
        'inventory-worker',
        'registry-security-worker',
        'maintenance-worker',
        'runtime-worker',
        'validation-worker',
        'analytics-worker',
        'reports-worker',
        'forecasting-worker',
        'resolver-execution-worker',
        'resolver-maintenance-worker',
        'beat',
    }
    for service in sorted(canonical_development_services):
        if f'  {service}:\n' not in development_source:
            errors.append(f'Dev Container compose does not define {service}.')
    if '--hostname=reports@%h' not in development_source:
        errors.append('Dev Container reports-worker has no canonical reports hostname.')

    if '--hostname=registry-security@%h' not in development_source:
        errors.append('Dev Container registry-security-worker has no canonical registry-security hostname.')

    production_source = (root / 'compose.production.yml').read_text(encoding='utf-8')
    if '--hostname=reports@%h' not in production_source:
        errors.append('Production reports-worker has no canonical reports hostname.')

    if '--hostname=registry-security@%h' not in production_source:
        errors.append('Production registry-security-worker has no canonical registry-security hostname.')

    devcontainer_config = json.loads((root / '.devcontainer' / 'devcontainer.json').read_text(encoding='utf-8'))
    run_services = set(devcontainer_config.get('runServices') or [])
    for service in sorted(canonical_development_services):
        if service not in run_services:
            errors.append(f'Dev Container runServices does not start {service}.')

    definitions_by_symbol = {f'{task.module}.{task.function}': task for task in tasks.values()}
    for symbol in sorted(discover_canonical_dispatch_targets(app_root)):
        task = definitions_by_symbol.get(symbol)
        if task is None:
            errors.append(f'Canonical dispatcher targets an unknown task symbol: {symbol}')
        elif 'job_execution_id' not in task.parameters:
            errors.append(f'Canonical dispatcher task does not accept injected job_execution_id: {symbol}')
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        errors = validate(root)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f'ERROR: {exc}')
        return 1
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    tasks = discover_tasks(root / 'app')
    _, routes = parse_celery_config(root / 'app' / 'config' / 'default.py')
    queues = parse_worker_queues(root / 'compose.production.yml')
    print(
        f'KAORI Celery topology is closed: {len(tasks)} tasks, '
        f'{len(routes)} explicit routes, {len(queues)} consumed queues.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
