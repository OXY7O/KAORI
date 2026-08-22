import re
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_notification_channel_registry_supports_telegram_email_and_microsoft_teams():
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    for key in ("'telegram'", "'email'", "'microsoft_teams'"):
        assert key in providers
    assert 'send_email_message' in providers
    assert 'send_microsoft_teams_message' in providers


def test_email_provider_supports_smtp_tls_modes_without_global_credentials():
    provider = read('app/integrations/delivery/notification_channels/providers/email.py')
    assert 'smtplib.SMTP_SSL' in provider
    assert 'client.starttls(' in provider
    assert 'client.send_message(email)' in provider
    assert "_EMAIL_SECURITY_MODES = {'starttls', 'tls', 'none'}" in provider
    assert "form.get('smtp_password')" in provider
    assert 'TELEGRAM_BOT_TOKEN' not in provider


def test_microsoft_teams_uses_workflows_webhook_and_keeps_url_secret():
    provider = read('app/integrations/delivery/notification_channels/providers/microsoft_teams.py')
    page = read('app/templates/integrations/delivery/notification_channels/providers/microsoft_teams/_form.html')
    assert "body = json.dumps({'text': _render_message(message)}" in provider
    assert "method='POST'" in provider
    assert "('.environment.api.powerplatform.com', '.logic.azure.com')" in provider
    assert 'legacy Office 365 connector webhook URLs' in page
    assert re.search(r'<input\b(?=[^>]*\bname="teams_workflow_url")(?=[^>]*\btype="password")[^>]*>', page)
    assert 'form_channel.teams_workflow_url' not in page


def test_notification_channels_redesign_surfaces_delivery_governance():
    page = read('app/templates/integrations/delivery/notification_channels/index.html')
    channels_workspace = read(
        'app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html'
    )
    channel_modals = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    workspace = page + channels_workspace + channel_modals
    for label in (
        'Delivery Providers',
        'Channel Registry',
        'Configured Channels',
        'Provider Setup Guide',
        'Delivery Contract',
        'Delivery Ownership',
    ):
        assert label in workspace
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    for provider in ('Telegram', 'Email', 'Microsoft Teams'):
        assert provider in providers
    assert 'platform delivery capability' in page.lower()
    definition = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')
    assert 'report.generated:' in definition
    assert 'automation.approval_required:' in definition
    assert 'automation.decision_approved:' in definition
    assert 'automation.decision_rejected:' in definition
    assert 'automation.execution_failed:' in definition


def test_provider_catalog_owns_setup_guidance_and_channel_tab_renders_one_guide_modal():
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')

    for field in (
        'setup_title: str',
        'setup_summary: str',
        'setup_requirements: tuple[str, ...]',
        'setup_steps: tuple[str, ...]',
        'security_note: str',
        'validation_note: str',
    ):
        assert field in providers
    assert 'Provider Setup Guide' in modal
    assert 'What You Need' in modal
    assert 'Configuration Sequence' in modal
    assert 'Credential & Security Boundary' in modal
    assert 'What Test Delivery Proves' in modal
    assert "guideProvider === '{{ provider.key }}'" in modal
    assert 'provider.setup_steps' in modal
    assert 'provider.setup_requirements' in modal
