from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ADAPTER = (ROOT / 'app/integrations/kubernetes/resolver_adapter.py').read_text()
CLIENT = (ROOT / 'app/integrations/kubernetes/client.py').read_text()


def test_adapter_is_allowlisted_and_declares_compatibility():
    assert "ACTION_KEY = 'kubernetes.deployment.restart'" in ADAPTER
    assert "CAPABILITY_KEY = 'kubernetes.deployments.patch'" in ADAPTER
    assert "COMPATIBILITY_PROFILE = 'kubernetes-v1'" in ADAPTER
    assert 'rollback_required = True' in ADAPTER


def test_adapter_requires_dry_run_rbac_preconditions_snapshot_and_post_condition():
    assert 'can_patch_deployments' in ADAPTER
    assert "dry_run='All' if dry_run else None" in ADAPTER
    assert "'resourceVersion': resource_version" in ADAPTER
    assert "'pre_change_snapshot': snapshot" in ADAPTER
    assert 'Deployment resourceVersion changed after dry-run.' in ADAPTER
    assert 'restart annotation could not be verified' in ADAPTER


def test_adapter_uses_canonical_runtime_and_self_subject_access_review():
    assert 'resolve_kubernetes_for_cluster' in ADAPTER
    assert 'create_self_subject_access_review' in ADAPTER
    assert 'AuthorizationV1Api' in CLIENT
    assert "field_manager='kaori-resolver'" in ADAPTER
    assert 'kubernetes_operations' not in ADAPTER
