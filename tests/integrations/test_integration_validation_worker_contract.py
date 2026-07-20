from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def route_block(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_validation_tasks_use_a_dedicated_celery_queue_and_worker() -> None:
    config = read('app/config/default.py')
    env = read('.env.example')
    dev_compose = read('.devcontainer/compose.devcontainer.yml')
    devcontainer = read('.devcontainer/devcontainer.json')
    production_compose = read('compose.production.yml')
    production_env = read('.env.production.example')
    production_validator = read('scripts/validate_production_env.py')

    assert "INTEGRATION_VALIDATION_CELERY_QUEUE" in config
    assert "'app.integrations.validation.tasks'" in config
    for task_name in (
        'validate_integration_instance',
        'validate_integration_binding',
        'refresh_integration_runtime_instance',
    ):
        assert f"app.integrations.validation.tasks.{task_name}" in config

    assert 'INTEGRATION_VALIDATION_CELERY_QUEUE=integration-validation' in env
    assert 'INTEGRATION_VALIDATION_WORKER_CONCURRENCY=1' in env
    assert 'INTEGRATION_VALIDATION_CELERY_QUEUE=integration-validation' in production_env
    assert 'INTEGRATION_VALIDATION_WORKER_CONCURRENCY=1' in production_env
    assert '"validation-worker"' in devcontainer
    assert "('INTEGRATION_VALIDATION_LOCK_TTL_SECONDS', 300)" in production_validator
    assert "('INTEGRATION_VALIDATION_WORKER_CONCURRENCY', 1)" in production_validator
    for compose in (dev_compose, production_compose):
        assert 'validation-worker:' in compose
        assert '--queues="$${INTEGRATION_VALIDATION_CELERY_QUEUE:-integration-validation}"' in compose


def test_runtime_architecture_documents_worker_and_dispatcher_boundaries() -> None:
    runtime_doc = read('docs/architecture/integration-runtime.md')
    integration_readme = read('app/integrations/README.md')

    assert 'Beat dispatcher only' in runtime_doc
    assert 'Celery Beat performs no provider I/O' in runtime_doc
    assert 'atomically blocks Full Validation from overlapping Runtime Refresh' in runtime_doc
    assert 'Test Connection' in integration_readme
    assert 'Full Capability Validation' in integration_readme
    assert 'Scope Binding Validation' in integration_readme


def test_manual_full_validation_routes_only_enqueue_and_poll() -> None:
    prom_routes = read('app/prometheus/routes.py')
    alert_routes = read('app/alertmanager/routes.py')
    tasks = read('app/integrations/validation/tasks.py')

    prom_block = route_block(
        prom_routes,
        'def instance_validate(instance_id: int)',
        "@prometheus_bp.get('/instances/<int:instance_id>/validate/status/",
    )
    alert_block = route_block(
        alert_routes,
        'def validate_instance(instance_id: int)',
        "@alertmanager_bp.get('/instances/<int:instance_id>/validate/status/",
    )
    assert 'enqueue_instance_validation(' in prom_block
    assert 'enqueue_instance_validation(' in alert_block
    assert 'refresh_and_record(' not in prom_block
    assert 'refresh_and_record(' not in alert_block
    assert 'validate_integration_instance' in tasks
    assert 'refresh_and_record(' in tasks
    assert 'prometheus_runtime_adapter' in tasks
    assert 'alertmanager_runtime_adapter' in tasks


def test_legacy_prometheus_cluster_validation_cannot_bypass_the_worker() -> None:
    routes = read('app/prometheus/routes.py')
    block = route_block(
        routes,
        'def validate_integration(\n    cluster_id: str,',
        "@prometheus_bp.get('/cluster/<string:cluster_id>/runtime/history')",
    )
    assert 'enqueue_instance_validation(' in block
    assert 'refresh_and_record(' not in block
    assert "url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation'" in block
    assert 'legacy_route' in block


def test_binding_validation_runs_in_worker_not_flask_request() -> None:
    prom_routes = read('app/prometheus/routes.py')
    alert_routes = read('app/alertmanager/routes.py')
    tasks = read('app/integrations/validation/tasks.py')

    prom_block = route_block(
        prom_routes,
        'def validate_instance_binding(instance_id: int, binding_id: int)',
        "@prometheus_bp.get('/instances/<int:instance_id>/bindings/<int:binding_id>/validate/status/",
    )
    alert_block = route_block(
        alert_routes,
        'def validate_binding(instance_id: int, binding_id: int)',
        "@alertmanager_bp.get('/instances/<int:instance_id>/bindings/<int:binding_id>/validate/status/",
    )
    assert 'enqueue_binding_validation(' in prom_block
    assert 'enqueue_binding_validation(' in alert_block
    assert 'validate_prometheus_binding(' not in prom_block
    assert 'validate_alertmanager_binding(' not in alert_block
    assert 'validate_prometheus_binding(instance=instance, binding=binding)' in tasks
    assert 'validate_alertmanager_binding(instance=instance, binding=binding)' in tasks


def test_runtime_monitoring_fans_out_lightweight_per_instance_jobs() -> None:
    dispatcher = read('app/integrations/runtime/tasks.py')
    tasks = read('app/integrations/validation/tasks.py')
    prometheus_service = read('app/prometheus/service.py')
    alertmanager_service = read('app/alertmanager/service.py')

    assert 'The Beat dispatcher intentionally performs no provider I/O.' in dispatcher
    assert 'enqueue_runtime_refresh(' in dispatcher
    assert 'refresh_and_record(' not in dispatcher
    assert 'refresh_integration_runtime_instance' in tasks
    assert 'PrometheusService(instance).refresh_runtime_health()' in tasks
    assert 'refresh_alertmanager_runtime_health(instance)' in tasks
    assert 'def _persist_failure_observation(' in tasks
    assert 'persist_runtime_state(' in tasks
    assert 'def refresh_runtime_health(self)' in prometheus_service
    assert 'def refresh_alertmanager_runtime_health(' in alertmanager_service


def test_full_validation_and_runtime_refresh_do_not_overlap_per_instance() -> None:
    web = read('app/integrations/validation/web.py')
    scheduled_tasks = read('app/integrations/validation/tasks.py')

    assert "if operation == 'full_validation':" in web
    assert "operation='runtime_refresh'" in web
    assert "operation='full_validation'" in web
    assert "operation='full_validation'" in scheduled_tasks
    assert "operation='runtime_refresh'" in scheduled_tasks
    state = read('app/integrations/validation/state.py')
    assert '_CLAIM_SCRIPT' in state
    assert 'conflicting_operations' in state
    assert "conflicting_operations=('runtime_refresh',)" in web
    assert "conflicting_operations=('full_validation',)" in web
    assert "conflicting_operations=('full_validation',)" in scheduled_tasks


def test_test_connection_remains_synchronous_and_lightweight() -> None:
    prom_routes = read('app/prometheus/routes.py')
    alert_routes = read('app/alertmanager/routes.py')

    prom_block = route_block(
        prom_routes,
        'def test_new_instance_connection()',
        "@prometheus_bp.get('/instances/<int:instance_id>/edit')",
    )
    alert_block = route_block(
        alert_routes,
        'def test_new_instance_connection()',
        "@alertmanager_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])",
    )
    assert 'test_prometheus_form_connection(form)' in prom_block
    assert 'enqueue_instance_validation(' not in prom_block
    assert 'test_alertmanager_form_connection(form)' in alert_block
    assert 'enqueue_instance_validation(' not in alert_block


def test_worker_job_lifecycle_is_audited_and_polled_with_htmx() -> None:
    prom_routes = read('app/prometheus/routes.py')
    alert_routes = read('app/alertmanager/routes.py')
    integration_routes = read('app/integrations/routes.py')
    tasks = read('app/integrations/validation/tasks.py')
    templates = '\n'.join(
        read(path)
        for path in (
            'app/templates/prometheus/partials/_detail_validation_content.html',
            'app/templates/prometheus/partials/_detail_scope.html',
            'app/templates/alertmanager/partials/_detail_validation_content.html',
            'app/templates/alertmanager/partials/_detail_scope.html',
            'app/templates/integrations/kubernetes/partials/_runtime_workspace.html',
        )
    )

    assert 'full_validation_queued' in prom_routes
    assert 'full_validation_queued' in alert_routes
    assert 'kubernetes_runtime_validation_queued' in integration_routes
    assert '_record_completion(' in tasks
    assert "queue_feedback=False" in tasks
    assert 'hx-trigger="load delay:1500ms"' in templates
    assert 'snapshot_feedback_for_user(snapshot, user_id=int(current_user.id))' in prom_routes
    assert 'snapshot_feedback_for_user(snapshot, user_id=int(current_user.id))' in alert_routes
    assert 'Completion toast feedback remains limited to the operator' in read('app/integrations/validation/web.py')
