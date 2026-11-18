from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from app.infrastructure_automation.source import (
    SOURCE_SHA,
    AutomationPilotDenied,
    normalize_facts,
    require_local_pilot_enabled,
    verify_localhost_source,
    verify_read_only_runner_stats,
)
from scripts.verify_celery_topology import parse_celery_config, parse_worker_queues, validate, validate_automation_pilot

ROOT = Path(__file__).resolve().parents[3]


def _app(environment: str) -> Flask:
    app = Flask(__name__)
    app.config['APP_ENV'] = environment
    return app


def test_disabled_without_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED', raising=False)
    with _app('development').app_context(), pytest.raises(AutomationPilotDenied, match='disabled'):
        require_local_pilot_enabled()


def test_production_rejected_even_if_flag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED', 'true')
    with _app('production').app_context(), pytest.raises(AutomationPilotDenied, match='non-production'):
        require_local_pilot_enabled()


def test_unapproved_source_denied_before_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED', 'true')
    with _app('development').app_context(), pytest.raises(AutomationPilotDenied, match='approved pilot SHA'):
        verify_localhost_source('/does/not/exist', '0' * 40)


def test_result_redaction_drops_unapproved_sensitive_facts() -> None:
    result = normalize_facts(
        [
            {
                'event': 'runner_on_ok',
                'event_data': {
                    'task_action': 'ansible.builtin.setup',
                    'res': {
                        'ansible_facts': {
                            'ansible_distribution': 'OracleLinux',
                            'ansible_kernel': '5.15.0',
                            'ansible_env': {'PASSWORD': 'not-for-evidence'},
                            'ansible_password': 'secret',
                        }
                    },
                },
            }
        ]
    )
    assert result == {'ansible_distribution': 'OracleLinux', 'ansible_kernel': '5.15.0'}


def test_runner_ok_without_facts_is_not_verified() -> None:
    with pytest.raises(AutomationPilotDenied, match='Required source-backed'):
        normalize_facts([{'event': 'runner_on_ok', 'event_data': {'task_action': 'shell'}}])


def test_source_revision_is_immutable_sha() -> None:
    assert len(SOURCE_SHA) == 40


@pytest.mark.parametrize(
    'stats',
    [
        None,
        {},
        {'ok': {'localhost': 1}},
        {'changed': {}, 'ok': {'worker-01': 1}},
        {'changed': {'localhost': 1}, 'ok': {'localhost': 1}},
        {'changed': {'localhost': 0}, 'ok': {'localhost': 1, 'other': 1}},
        {'changed': {}, 'ok': {'localhost': 1}, 'failures': {'localhost': 1}},
        {'changed': {}, 'ok': {'localhost': 1}, 'dark': {'localhost': 1}},
    ],
)
def test_runner_stats_reject_unsafe_or_unproven_execution(stats: object) -> None:
    with pytest.raises(AutomationPilotDenied):
        verify_read_only_runner_stats(stats)


@pytest.mark.parametrize('changed', ({}, {'localhost': 0}))
def test_runner_stats_accept_successful_unchanged_localhost(changed: dict[str, int]) -> None:
    verify_read_only_runner_stats({'changed': changed, 'ok': {'localhost': 1}, 'failures': {}, 'dark': {}})


def _pilot_topology() -> dict[str, Any]:
    config_path = ROOT / 'app' / 'config' / 'default.py'
    production = ROOT / 'compose.production.yml'
    development = ROOT / '.devcontainer' / 'compose.devcontainer.yml'
    _, routes = parse_celery_config(config_path)
    return {
        'routes': routes,
        'dockerfile': (ROOT / 'Dockerfile').read_text(encoding='utf-8'),
        'config_source': config_path.read_text(encoding='utf-8'),
        'default_compose_source': production.read_text(encoding='utf-8')
        + '\n'
        + development.read_text(encoding='utf-8'),
        'default_worker_queues': parse_worker_queues(production) | parse_worker_queues(development),
    }


def test_automation_celery_topology_is_closed_without_default_worker_activation() -> None:
    assert validate(ROOT) == []
    assert validate_automation_pilot(**_pilot_topology()) == []


@pytest.mark.parametrize(
    ('old', 'new'),
    [
        ('FROM base AS automation-worker', 'FROM base AS missing-worker'),
        ('--queues=automation', '--queues=automation,inventory'),
        ('--concurrency=1', '--concurrency=2'),
        ('--prefetch-multiplier=1', '--prefetch-multiplier=2'),
        ('--hostname=automation@%h', '--hostname=inventory@%h'),
        ('USER kaori\nCMD ["celery"', 'USER root\nCMD ["celery"'),
        ('FROM base AS production', 'FROM automation-worker AS production'),
        ('COPY requirements/automation-worker.txt /tmp/requirements/automation-worker.txt', '# missing manifest'),
    ],
)
def test_automation_topology_rejects_missing_or_drifted_isolated_worker(old: str, new: str) -> None:
    topology = _pilot_topology()
    assert old in topology['dockerfile']
    topology['dockerfile'] = topology['dockerfile'].replace(old, new, 1)
    assert validate_automation_pilot(**topology)


@pytest.mark.parametrize(
    'route_change',
    [
        {'app.infrastructure_automation.tasks.collect_localhost_facts': 'inventory'},
        {'app.infrastructure_automation.tasks.materialize_kubespray_plan_review': 'default'},
        {'app.kubernetes.cluster.tasks.sync_all_clusters': 'automation'},
    ],
)
def test_automation_topology_rejects_wrong_or_unrelated_task_routes(route_change: dict[str, str]) -> None:
    topology = _pilot_topology()
    topology['routes'].update(route_change)
    assert validate_automation_pilot(**topology)


def test_automation_topology_rejects_default_worker_and_beat_activation() -> None:
    topology = _pilot_topology()
    topology['default_worker_queues'].add('automation')
    assert validate_automation_pilot(**topology)

    topology = _pilot_topology()
    topology['default_compose_source'] += '\n  automation-worker:\n'
    assert validate_automation_pilot(**topology)

    topology = _pilot_topology()
    topology['config_source'] += (
        "\nunsafe_schedule = {'task': 'app.infrastructure_automation.tasks.collect_localhost_facts'}\n"
    )
    assert validate_automation_pilot(**topology)


def test_ordinary_celery_queues_still_require_both_default_consumers(monkeypatch: pytest.MonkeyPatch) -> None:
    def without_ordinary_worker(path: Path) -> set[str]:
        return parse_worker_queues(path) - {'reports'}

    monkeypatch.setattr('scripts.verify_celery_topology.parse_worker_queues', without_ordinary_worker)
    errors = validate(ROOT)
    assert 'Celery routed queue has no production worker: reports' in errors
    assert 'Celery routed queue has no Dev Container worker: reports' in errors
