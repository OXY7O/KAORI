"""Kubernetes Admin aggregate is SQL-first and never decrypts fleet kubeconfig."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_admin_read_model_uses_canonical_binding_and_sql_counts():
    sql = (ROOT / 'app/platform_operations/kubernetes/read_model.py').read_text()
    overview = (ROOT / 'app/platform_operations/kubernetes/presentation.py').read_text()
    for token in (
        "binding.asset_type == 'kubernetes_cluster'",
        "canonical.lifecycle_status == 'active'",
        'connection.cluster_id == Cluster.id',
        'connection.kubeconfig.is_not(None)',
        'Cluster.secret_reveal_encryption_verified.is_(True)',
        'Cluster.secret_reveal_audit_verified.is_(True)',
        'func.count(Cluster.id)',
    ):
        assert token in sql
    assert 'administration_counts()' in overview
    assert 'Cluster.query.order_by(' not in overview
    assert 'kubeconfig_for_cluster(' not in overview


def test_namespace_pagination_reuses_canonical_contract():
    service = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/service.py').read_text()
    assert 'build_pagination_window(' in service
    assert 'pagination_payload(window)' in service
    assert 'filtered_namespace_rows[window.offset : window.offset + window.per_page]' in service
