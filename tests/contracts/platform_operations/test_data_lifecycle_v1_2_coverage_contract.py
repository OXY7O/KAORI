from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_observations_share_one_provider_neutral_lifecycle() -> None:
    domain = read('app/retention/domains/runtime_observation.py')
    presentation = read('app/retention/presentation.py')
    shared_history = read('app/templates/integrations/partials/_runtime_history.html')
    prometheus = read('app/templates/prometheus/partials/_runtime_history.html')
    alertmanager = read('app/templates/alertmanager/partials/_runtime_history.html')
    kubernetes = read('app/templates/integrations/kubernetes/detail.html')

    assert 'IntegrationRuntimeObservation' in domain
    assert 'IntegrationRuntimeObservation.provider ==' not in domain
    assert 'filter_by(provider=' not in domain
    assert "'label': 'Kubernetes'" in presentation
    assert "'label': 'Prometheus'" in presentation
    assert "'label': 'Alertmanager'" in presentation
    assert "domain='runtime_observation'" in shared_history
    assert "include 'integrations/partials/_runtime_history.html'" in prometheus
    assert "include 'integrations/partials/_runtime_history.html'" in alertmanager
    assert "include 'integrations/partials/_runtime_history.html'" in kubernetes


def test_activity_audit_and_user_notifications_share_one_lifecycle_source() -> None:
    domain = read('app/retention/domains/operational_activity.py')
    queries = read('app/notifications/queries.py')
    presentation = read('app/retention/presentation.py')
    activity = read('app/templates/notifications/activity.html')
    center = read('app/templates/notifications/partials/_center_page_content.html')

    assert "source_model = 'notifications'" in domain
    assert 'Notification.query.filter(Notification.id.in_(record_ids))' in domain
    assert 'deck_visible' not in domain
    assert 'Notification.deck_visible.is_(True)' in queries
    assert "'label': 'Activity Audit Table'" in presentation
    assert "'label': 'Notification Center'" in presentation
    assert "'label': 'Authentication Audit'" in presentation
    assert 'Activity Audit and persistent Notification Center records share the same archive-first policy' in activity
    assert 'Persistent notifications share the Activity Audit retention policy.' in center
    assert 'Transient toasts remain outside Data Lifecycle.' in center


def test_data_lifecycle_exposes_coverage_instead_of_new_parallel_domains() -> None:
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    registry = read('app/retention/domains/__init__.py')

    assert 'Lifecycle Coverage' in workspace
    assert 'Records covered by this retention, archive, and cleanup policy.' in workspace
    assert 'Coverage:' in workspace
    assert 'Excluded:' in workspace
    assert "'operational_activity': OperationalActivityArchiveDomain" in registry
    assert "'job_execution': JobExecutionArchiveDomain" in registry
    assert "'runtime_observation': RuntimeObservationArchiveDomain" in registry
    assert "'analytics_snapshot': AnalyticsSnapshotArchiveDomain" in registry
