from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_system_runbook_catalog_is_source_controlled_and_starts_with_validated_restart():
    catalog = read('app/definitions/catalogs/intelligence/knowledge/system_runbooks.yaml')
    adapter = read('app/intelligence/knowledge/system_catalog.py')

    assert 'schema_version: 1' in catalog
    assert 'kind: system_runbooks' in catalog
    assert 'runbook_key: kubernetes.deployment.restart' in catalog
    assert 'validation_status: system_tested' in catalog
    assert 'maturity: validated' in catalog
    assert 'approval_policy: needs_approval' in catalog
    assert '- kubernetes.deployments.patch' in catalog
    assert '- kubernetes-v1' in catalog
    assert 'mode: manual_compensating_recovery' in catalog
    assert 'post-action rollout verification' in catalog.lower()
    assert "load_definition_document('intelligence/knowledge/system_runbooks.yaml'" in adapter
    assert 'SYSTEM_RUNBOOK_CATALOG = _load_system_runbooks()' in adapter


def test_system_catalog_activation_is_idempotent_and_fails_closed_on_contract_drift():
    service = read('app/intelligence/knowledge/service.py')
    routes = read('app/intelligence/automation_control/routes.py')
    bootstrap = read('app/integrations/resolver_bootstrap.py')
    assert 'def activate_system_runbook(' in service
    assert 'revision.content_hash != definition.content_hash' in service
    assert 'catalog drift detected' in service.lower()
    assert "revision.publication_status == 'published'" in service
    assert "'/automation-control/system-runbooks/<string:runbook_key>/activate'" in routes
    assert 'activate_system_runbook(' in routes
    assert 'build_resolver_contract_registry()' in routes
    assert 'def build_resolver_contract_registry()' in bootstrap
    assert 'CATALOG_VALIDATION_NAMESPACE' in bootstrap


def test_custom_authoring_is_locked_but_legacy_endpoints_fail_closed():
    config = read('app/config/default.py')
    routes = read('app/intelligence/automation_control/routes.py')
    template = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    validator = read('scripts/validate_production_env.py')
    assert "CUSTOM_RUNBOOK_AUTHORING_ENABLED = _env_bool('CUSTOM_RUNBOOK_AUTHORING_ENABLED', False)" in config
    assert 'assert_custom_runbook_authoring_enabled(current_app.config)' in routes
    assert 'assert_binding_uses_allowed_runbook(revision, config=current_app.config)' in routes
    assert 'Custom Authoring Locked' in template
    assert 'Execution Resolver Disabled' in template
    assert 'Create Runbook' not in template
    assert 'Create Revision' not in template
    assert 'CUSTOM_RUNBOOK_AUTHORING_ENABLED must remain false in production' in validator


def test_system_runbook_bindings_can_be_paused_without_deleting_governance_evidence():
    routes = read('app/intelligence/automation_control/routes.py')
    matching = read('app/intelligence/knowledge/matching.py')
    template = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    assert "'/automation-control/bindings/<int:binding_id>/status'" in routes
    assert 'set_alert_binding_status(' in routes
    assert 'def set_alert_binding_status(' in matching
    assert "lifecycle_status not in {'active', 'disabled'}" in matching
    assert 'Disable Binding' in template
    assert 'Enable Binding' in template
