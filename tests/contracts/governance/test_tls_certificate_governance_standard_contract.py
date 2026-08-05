from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tls_collection_uses_explicit_evidence_and_safe_identity() -> None:
    collector = read('app/governance/tls_certificates/collector.py')

    assert 'class TLSCollectionEvidence' in collector
    assert 'def _has_secret_identity(' in collector
    assert 'if secret.type == TLS_SECRET_TYPE and _has_secret_identity(secret)' in collector
    assert 'unique_consumers:' in collector
    assert 'Unexpected Kubernetes collection failure.' in collector
    assert "str(exc) or 'Kubernetes collection failed.'" not in collector


def test_tls_mutation_is_resource_version_bound_and_scrubbed() -> None:
    mutation = read('app/governance/tls_certificates/mutation.py')

    assert 'read_namespaced_secret(' in mutation
    assert "for dry_run in ('All', None)" in mutation
    assert "'metadata': {'resourceVersion': resource_version}" in mutation
    assert 'scrub_secret_payload(response)' in mutation
    assert 'scrub_mapping_values(encoded_data)' in mutation
    assert '.query.get(' not in mutation


def test_tls_workspace_and_progress_are_canonical() -> None:
    workspace = read('app/templates/governance/tls_certificates/partials/_page_workspace.html')
    progress = read('app/templates/governance/tls_certificates/partials/_sync_progress_toast.html')

    assert 'id="tls-certificates-page-workspace"' in workspace
    assert "partial_mode='page_workspace'" in workspace
    assert '_sync_progress_toast.html' in workspace
    assert 'components/operational_progress_toast.html' in progress
    assert not (ROOT / 'app/governance/tls_certificates/toast.py').exists()
    assert not (ROOT / 'app/templates/governance/tls_certificates/partials/_inventory_scope.html').exists()


def test_tls_terminal_delivery_precedes_job_completion() -> None:
    tasks = read('app/governance/tls_certificates/tasks.py')
    presentation = read('app/governance/tls_certificates/job_presentation.py')

    assert tasks.index('deck_user_ids = _notify_requesters(') < tasks.index('context.succeed(')
    assert "result['activity_audit_saved']" in tasks
    assert "result['notification_deck_user_ids']" in tasks
    assert 'notification_deck_visible = (' in presentation


def test_tls_sync_distinguishes_mapping_warning_from_fatal_collection_failure() -> None:
    service = read('app/governance/tls_certificates/service.py')
    tasks = read('app/governance/tls_certificates/tasks.py')
    results = read('app/governance/tls_certificates/results.py')

    assert 'class TLSClusterSyncResult' in service
    assert 'fatal_error: str | None' in service
    assert 'warning: str | None' in service
    assert "'warning_cluster_count'" in tasks
    assert 'warning_count: int = 0' in results
    assert 'if failures or warnings:' in results


def test_tls_notification_delivery_audit_records_the_final_matrix() -> None:
    audit = read('docs/design/audits/KUBERNETES_TLS_NOTIFICATION_DELIVERY_AUDIT_2026_08.md')

    for token in ('`audit_only`', '`deck_on_failure`', '`persistent`', '20260805_notification_deck_v2'):
        assert token in audit
