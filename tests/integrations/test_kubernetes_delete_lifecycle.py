from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_cluster_delete_detaches_history_and_removes_scope_bindings():
    service = _read('app/cluster/service.py')
    block = service.split('def delete_cluster(', 1)[1].split('\ndef build_cluster_context(', 1)[0]

    assert 'Report.query.filter(Report.cluster_id == cluster_id)' in block
    assert 'ReportSchedule.query.filter(ReportSchedule.cluster_id == cluster_id)' in block
    assert "IntegrationBinding.asset_type == 'kubernetes_cluster'" in block
    assert 'IntegrationBinding.asset_key == cluster_id' in block
    assert 'PrometheusBinding' not in block
    assert 'AlertmanagerBinding' not in block


def test_cluster_delete_removes_only_kubernetes_canonical_instance():
    service = _read('app/cluster/service.py')
    block = service.split('def delete_cluster(', 1)[1].split('\ndef build_cluster_context(', 1)[0]

    assert 'db.session.delete(cluster)' in block
    assert 'db.session.flush()' in block
    assert 'db.session.delete(canonical)' in block
    assert 'db.session.delete(prometheus' not in block.lower()
    assert 'db.session.delete(alertmanager' not in block.lower()


def test_cluster_delete_route_rolls_back_failed_transaction_before_feedback():
    routes = _read('app/cluster/routes.py')
    block = routes.split('def delete_cluster_route(', 1)[1]
    failure_block = block.split('except Exception as exc:', 1)[1].split('else:', 1)[0]

    assert 'db.session.rollback()' in failure_block
    assert failure_block.index('db.session.rollback()') < failure_block.index('record_operational_activity(')


def test_kubernetes_delete_modal_posts_csrf_protected_request():
    modal = _read('app/templates/integrations/kubernetes/partials/_delete_modal.html')

    assert 'x-bind:action="deleteUrl"' in modal or ':action="deleteUrl"' in modal
    assert 'method="POST"' in modal
    assert 'name="csrf_token"' in modal
