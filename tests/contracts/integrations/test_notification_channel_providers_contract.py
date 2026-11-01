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
    catalog = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    assert 'legacy Office 365 connector ' in catalog
    assert 'webhook URLs.' in catalog
    assert '<p class="mt-1 text-xs leading-5 text-content-muted">' not in page
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
        'Channel Registry',
        'Configured Channels',
        'Provider Setup Guide',
        'Delivery Contract',
        'Delivery Governance',
        'Channel Readiness',
        'Delivery Outcomes',
        'Recent Delivery',
    ):
        assert label in workspace
    assert 'Delivery Providers' not in page
    assert '{% for provider in payload.providers %}' in channels_workspace
    assert 'Open {{ provider.label }} setup guide' in channels_workspace
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


def test_all_notification_channel_configuration_guides_are_provider_owned() -> None:
    catalog = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    keys = ('discord', 'slack', 'ntfy', 'telegram', 'email', 'microsoft_teams')

    assert 'configuration_guide_summary: str' in catalog
    assert 'configuration_guide_items: tuple[str, ...]' in catalog
    assert catalog.count('configuration_guide_summary=(') == len(keys)
    assert catalog.count('configuration_guide_items=(') == len(keys)
    assert "'configuration_guide_summary': adapter.configuration_guide_summary" in catalog
    assert "'configuration_guide_items': list(adapter.configuration_guide_items)" in catalog
    assert "'notification-' ~ provider_option.key ~ '-configuration-guide'" in modal
    assert 'provider_option.configuration_guide_summary' in modal
    assert 'items=provider_option.configuration_guide_items' in modal
    assert "variant='guide'" in modal
    assert "provider_option.key == 'telegram'" not in modal

    for key in keys:
        form = read(f'app/templates/integrations/delivery/notification_channels/providers/{key}/_form.html')
        assert '<p class="mt-1 text-xs leading-5 text-content-muted">' not in form
        assert 'info_tip.render(' not in form
        assert 'sm:grid-cols-2' in form

    ntfy = read('app/templates/integrations/delivery/notification_channels/providers/ntfy/_form.html')
    email = read('app/templates/integrations/delivery/notification_channels/providers/email/_form.html')
    assert 'lg:grid-cols-3' in ntfy and 'lg:grid-cols-3' in email
    assert 'sm:col-span-2' not in ntfy
    assert 'sm:col-span-2' in email

    for guidance in (
        'Human-readable name; the webhook decides which Discord channel receives ',
        'Channel-bound official Slack URL; never rendered back.',
        'NOTIFICATION_NTFY_ALLOWED_ORIGINS',
        'Changing this requires a new Test Delivery.',
        'Separate multiple recipients with commas.',
        'not legacy Office 365 connector ',
    ):
        assert guidance in catalog
