"""GitHub App setup inherits KAORI integration UX and security boundaries."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_onboarding_reuses_shared_kaori_components_not_new_css() -> None:
    landing = _source('app/templates/integrations/source_control/github/index.html')
    form = _source('app/templates/integrations/source_control/github/form.html')
    workspace = _source('app/templates/integrations/partials/_domain_workspace.html')
    assert 'components/page_hero.html' in landing
    assert 'integrations/components/_provider_frontpage.html' in landing
    assert 'integrations/components/_provider_registration_hero.html' in form
    assert 'integrations/components/_workspace.html' in form
    assert 'integration_ui.section_shell_classes()' in form
    assert "domain.key == 'source_control'" in workspace
    assert "url_for('github_source.index')" in workspace
    assert '<style' not in landing and '<style' not in form
    assert 'text-kaori-primary' in landing
    assert 'bg-kaori-primary' in form


def test_form_is_csrf_protected_and_admission_gated_in_ui() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    assert 'form.hidden_tag()' in form
    assert 'fieldset' in form and 'not available' in form
    assert 'action" value="test"' in form
    assert 'action" value="save"' in form
    assert 'disabled' in form
    assert 'autocomplete="off"' in form
    assert 'form.webhook_secret' in form and 'form.private_key_pem' in form


def test_server_checks_rbac_and_blocks_post_before_reading_secrets() -> None:
    routes = _source(
        'app/integrations/source_control/source_control/providers/github/application/routes.py'
    )
    assert "@permission_required('integrations.manage')" in routes
    assert "if request.method == 'POST' and not available:" in routes
    assert 'abort(409)' in routes
    assert 'form.validate_on_submit()' in routes
    assert 'form.clear_sensitive_fields()' in routes
    assert "'Cache-Control'] = 'no-store, max-age=0'" in routes
    assert 'record_operational_activity(' in routes
    assert 'save_tested_connection(values)' in routes


def test_planned_provider_does_not_fake_inventory_zero_or_ready() -> None:
    routes = _source(
        'app/integrations/source_control/source_control/providers/github/application/routes.py'
    )
    landing = _source('app/templates/integrations/source_control/github/index.html')
    assert 'registered: int | None = None' in routes
    assert 'ready: int | None = None' in routes
    assert 'if available:' in routes
    assert 'Not Observed' in landing
    assert 'Not Admitted' in landing
    assert 'Provider Admission' in landing


def test_blueprint_is_registered_using_existing_bootstrap() -> None:
    bootstrap = _source('app/bootstrap/blueprints.py')
    assert 'from app.integrations.source_control.source_control.providers.github.application.routes import github_source_bp' in bootstrap
    assert 'github_source_bp,' in bootstrap
    assert "url_prefix='/integrations/source-control/github'" in _source(
        'app/integrations/source_control/source_control/providers/github/application/routes.py'
    )
