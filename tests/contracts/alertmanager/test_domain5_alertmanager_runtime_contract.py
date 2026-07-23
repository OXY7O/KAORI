from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_validation_workers_enforce_operational_lifecycle_before_provider_io():
    source = (ROOT / 'app/integrations/validation/tasks.py').read_text()
    assert 'def _ensure_instance_operational(' in source
    assert "_ensure_instance_operational(instance, provider_type='alertmanager')" in source
    assert '_ensure_instance_operational(instance, provider_type=provider_type)' in source
    assert "if not binding.enabled:" in source


def test_alertmanager_resolution_blocks_non_active_canonical_identity():
    source = (ROOT / 'app/alertmanager/resolver.py').read_text()
    assert "lifecycle_eligible = canonical_enabled and lifecycle == 'active'" in source
    assert 'and lifecycle_eligible' in source
    assert 'blocks source selection' in source
