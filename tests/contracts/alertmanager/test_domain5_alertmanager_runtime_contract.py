from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_validation_workers_enforce_operational_lifecycle_before_provider_io() -> None:
    source = (ROOT / 'app/integrations/validation/tasks.py').read_text()
    assert 'def _ensure_instance_operational(' not in source
    assert "ensure_provider_operational(instance, provider_type='alertmanager')" in source
    assert 'ensure_provider_operational(instance, provider_type=provider_type)' in source



def test_alertmanager_resolution_blocks_non_active_canonical_identity():
    source = (ROOT / 'app/alertmanager/resolver.py').read_text()
    assert "lifecycle_eligible = canonical_enabled and lifecycle == 'active'" in source
    assert 'and lifecycle_eligible' in source
    assert 'blocks source selection' in source
