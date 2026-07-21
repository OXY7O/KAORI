from pathlib import Path


def test_runtime_observations_are_not_pruned_at_write_time() -> None:
    repository = Path('app/integrations/runtime/repository.py').read_text(encoding='utf-8')
    history = Path('app/templates/integrations/partials/_runtime_history.html').read_text(encoding='utf-8')
    assert 'prune_runtime_history' not in repository
    assert 'MAX_RUNTIME_OBSERVATIONS_PER_INSTANCE' not in repository
    assert "'retention_limit'" not in repository
    assert 'Retention is governed centrally by KAORI Data Lifecycle.' in history
    assert "domain='runtime_observation'" in history
    assert 'Manage Lifecycle' in history
    assert '>Rows per page<' not in history
    assert 'aria-label="Runtime observations per page"' in history


def test_runtime_observation_is_an_active_data_lifecycle_domain() -> None:
    domains = Path('app/retention/domains/__init__.py').read_text(encoding='utf-8')
    adapter = Path('app/retention/domains/runtime_observation.py').read_text(encoding='utf-8')
    presentation = Path('app/retention/presentation.py').read_text(encoding='utf-8')
    config = Path('app/config/default.py').read_text(encoding='utf-8')
    assert "'runtime_observation': RuntimeObservationArchiveDomain" in domains
    assert "name = 'runtime_observation'" in adapter
    assert 'IntegrationRuntimeObservation.observed_at < cutoff_at' in adapter
    assert "'runtime_observation':'Runtime Observations'" in presentation
    assert "'runtime_observation':'Provider health, readiness, latency, and capability-drift evidence.'" in presentation
    assert 'RUNTIME_OBSERVATION_RETENTION_DAYS' in config
    assert 'operational_activity,job_execution,runtime_observation' in config
