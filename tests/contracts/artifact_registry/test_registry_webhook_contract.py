from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_webhook_admission_hashes_credentials_and_payloads() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    service = (ROOT / 'app/artifact_registry/webhooks.py').read_text()
    configuration = (ROOT / 'app/integrations/registry/webhook_configuration.py').read_text()

    assert 'class RegistryWebhookEndpoint' in models
    assert 'token_digest' in models
    assert 'class RegistryWebhookEvent' in models
    assert 'payload_digest' in models
    assert 'raw_payload' not in models
    assert 'hashlib.sha256(token.encode()).hexdigest()' in configuration
    assert 'hashlib.sha256(token.encode()).hexdigest()' not in service
    assert 'payload_retained' in service
    assert 'enqueue_registry_target_refresh' in service


def test_webhook_is_fast_path_not_inventory_truth() -> None:
    service = (ROOT / 'app/artifact_registry/webhooks.py').read_text()
    jobs = (ROOT / 'app/artifact_registry/sync_jobs.py').read_text()
    registered = (ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text()

    assert "trigger_type='webhook'" in service
    assert 'enqueue_registry_target_refresh' in jobs
    assert 'artifact_registry.inventory.sync' in registered
    assert 'default_interval_minutes: 60' in registered


def test_webhook_event_dedup_is_persisted() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    service = (ROOT / 'app/artifact_registry/webhooks.py').read_text()

    assert "name='uq_registry_webhook_event_dedup'" in models
    assert 'dedup_key' in service
    assert 'duplicate' in service.lower()


def test_webhook_configuration_is_owned_by_harbor_connection_workspace() -> None:
    governance = (ROOT / 'app/templates/artifact_registry/governance.html').read_text()
    configuration = (
        ROOT / 'app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html'
    ).read_text()
    harbor_routes = (ROOT / 'app/integrations/registry/providers/harbor/application/routes.py').read_text()
    registry_routes = (ROOT / 'app/artifact_registry/routes.py').read_text()

    assert 'Webhook Reconciliation' in configuration
    assert "url_for('artifact_registry.webhook_receive'" in configuration
    assert "url_for('harbor.webhook_token'" in configuration
    assert "url_for('harbor.webhook_disable'" in configuration
    assert 'def webhook_token(instance_id: int)' in harbor_routes
    assert 'def webhook_disable(instance_id: int)' in harbor_routes
    assert 'def webhook_receive(integration_instance_id: int)' in registry_routes
    assert 'Generate Token' not in governance
    assert 'Webhook Admission' not in governance


def test_webhook_ui_distinguishes_admission_from_delivery() -> None:
    configuration = (
        ROOT / 'app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html'
    ).read_text()

    assert 'Webhook Reconciliation' in configuration
    assert 'request a targeted Inventory refresh' in configuration
    assert 'Scheduled reconciliation remains the correctness and recovery path.' in configuration
    assert 'Webhook Admission' in configuration
    assert 'Ready means webhook admission is configured.' in configuration
    assert 'It does not verify Harbor delivery or a completed Inventory refresh.' in configuration
    assert 'No event received yet' in configuration


def test_webhook_receiver_guidance_is_safe_and_localhost_aware() -> None:
    configuration = (
        ROOT / 'app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html'
    ).read_text()
    receiver = (ROOT / 'app/artifact_registry/routes.py').read_text()
    auth = (ROOT / 'app/artifact_registry/webhooks.py').read_text()

    assert 'Webhook Receiver URL' in configuration
    assert "url_for('artifact_registry.webhook_receive'" in configuration
    assert "request.host.split(':', 1)[0]|lower" in configuration
    assert "receiver_host in ['localhost', '127.0.0.1']" in configuration
    assert "request.host.startswith('[::1]')" in configuration
    assert 'a Harbor-reachable HTTPS address' in configuration
    assert 'Authorization: Bearer &lt;token&gt;' in configuration
    assert 'X-KAORI-Webhook-Token: &lt;token&gt;' in configuration
    assert 'The token is displayed only when generated or rotated.' in configuration
    assert "request.headers.get('X-KAORI-Webhook-Token')" in receiver
    assert "authorization.lower().startswith('bearer ')" in receiver
    assert 'hmac.compare_digest' in auth
    assert 'hx-post=' in configuration
    assert 'name="csrf_token"' in configuration
    assert "url_for('harbor.webhook_disable'" in configuration
