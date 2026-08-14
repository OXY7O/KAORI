from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/inventory/kubernetes/job_adapter.py'


class _DispatchResult:
    def __init__(self, *, status, message, job=None, created=False) -> None:
        self.status = status
        self.message = message
        self.job = job
        self.created = created

    @property
    def accepted(self) -> bool:
        return self.job is not None


class _ClusterQuery:
    def __init__(self, cluster) -> None:
        self.cluster = cluster
        self.cluster_id: str | None = None

    def filter_by(self, **kwargs):
        self.cluster_id = kwargs.get('id')
        return self

    def first(self):
        return self.cluster


def _load_adapter(monkeypatch, *, cluster, enqueue_cluster, enqueue_fleet):
    app_module = ModuleType('app')
    cluster_package = ModuleType('app.cluster')
    sync_jobs = ModuleType('app.cluster.sync_jobs')
    common_package = ModuleType('app.common')
    common_presentation = ModuleType('app.common.job_execution_presentation')
    jobs_package = ModuleType('app.jobs')
    jobs_constants = ModuleType('app.jobs.constants')
    jobs_definitions = ModuleType('app.jobs.definitions')
    jobs_definition_base = ModuleType('app.jobs.definitions.base')
    jobs_policies = ModuleType('app.jobs.policies')
    jobs_policy_presentation = ModuleType('app.jobs.policies.presentation')
    models_package = ModuleType('app.models')
    models_cluster = ModuleType('app.models.cluster')
    models_job = ModuleType('app.models.job')

    class NoEligibleInventoryTargets(RuntimeError):
        pass

    cluster_model = SimpleNamespace(query=_ClusterQuery(cluster))
    sync_jobs.NoEligibleInventoryTargets = NoEligibleInventoryTargets
    sync_jobs.build_fleet_inventory_targets = lambda **_kwargs: []
    sync_jobs.enqueue_all_cluster_inventory_sync = enqueue_fleet
    sync_jobs.enqueue_cluster_inventory_sync = enqueue_cluster
    common_presentation.present_job_execution = lambda _job: {}
    jobs_constants.ACTIVE_JOB_STATUSES = ()
    jobs_definition_base.RegisteredJobDispatchResult = _DispatchResult
    jobs_policy_presentation.present_interval = lambda value: str(value)
    models_cluster.Cluster = cluster_model
    models_job.JobExecution = object
    models_job.JobPolicy = object

    modules = {
        'app': app_module,
        'app.cluster': cluster_package,
        'app.cluster.sync_jobs': sync_jobs,
        'app.common': common_package,
        'app.common.job_execution_presentation': common_presentation,
        'app.jobs': jobs_package,
        'app.jobs.constants': jobs_constants,
        'app.jobs.definitions': jobs_definitions,
        'app.jobs.definitions.base': jobs_definition_base,
        'app.jobs.policies': jobs_policies,
        'app.jobs.policies.presentation': jobs_policy_presentation,
        'app.models': models_package,
        'app.models.cluster': models_cluster,
        'app.models.job': models_job,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = spec_from_file_location('inventory_job_adapter_contract', MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, cluster_model.query


def test_cluster_scoped_dispatch_uses_canonical_single_cluster_sync(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1', name='Staging')
    calls: list[dict[str, object]] = []
    job = SimpleNamespace(public_id='job-1')

    def enqueue_cluster(**kwargs):
        calls.append(kwargs)
        return job, True

    module, query = _load_adapter(
        monkeypatch,
        cluster=cluster,
        enqueue_cluster=enqueue_cluster,
        enqueue_fleet=lambda **_kwargs: None,
    )

    result = module.dispatch_inventory_sync(
        requested_by_user_id=None,
        trigger_type='recovery',
        parameters={'cluster_id': ' cluster-1 '},
    )

    assert query.cluster_id == 'cluster-1'
    assert calls == [
        {
            'cluster': cluster,
            'requested_by_user_id': None,
            'trigger_type': 'recovery',
        }
    ]
    assert result.status == 'queued'
    assert result.job is job
    assert result.created is True
    assert result.accepted is True


def test_cluster_scoped_dispatch_blocks_deleted_cluster(monkeypatch) -> None:
    fleet_calls: list[bool] = []
    module, query = _load_adapter(
        monkeypatch,
        cluster=None,
        enqueue_cluster=lambda **_kwargs: None,
        enqueue_fleet=lambda **_kwargs: fleet_calls.append(True),
    )

    result = module.dispatch_inventory_sync(
        requested_by_user_id=7,
        trigger_type='manual',
        parameters={'cluster_id': 'missing-cluster'},
    )

    assert query.cluster_id == 'missing-cluster'
    assert result.status == 'blocked'
    assert result.accepted is False
    assert 'no longer exists' in result.message
    assert fleet_calls == []
