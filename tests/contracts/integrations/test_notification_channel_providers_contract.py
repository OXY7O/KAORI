from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_notification_channel_registry_supports_telegram_email_and_microsoft_teams():
    providers = read('app/notification_channels/providers/__init__.py')
    for key in ("'telegram'", "'email'", "'microsoft_teams'"):
        assert key in providers
    assert 'send_email_message' in providers
    assert 'send_microsoft_teams_message' in providers


def test_email_provider_supports_smtp_tls_modes_without_global_credentials():
    provider = read('app/notification_channels/providers/email.py')
    forms = read('app/notification_channels/forms.py')
    assert 'smtplib.SMTP_SSL' in provider
    assert 'client.starttls(' in provider
    assert 'client.send_message(email)' in provider
    assert "_EMAIL_SECURITY_MODES = {'starttls', 'tls', 'none'}" in forms
    assert "'smtp_password'" in forms
    assert 'TELEGRAM_BOT_TOKEN' not in provider


def test_microsoft_teams_uses_workflows_webhook_and_keeps_url_secret():
    provider = read('app/notification_channels/providers/microsoft_teams.py')
    forms = read('app/notification_channels/forms.py')
    page = read('app/templates/integrations/notification_channels/index.html')
    assert "body = json.dumps({'text': _render_message(message)}" in provider
    assert "method='POST'" in provider
    assert "('.environment.api.powerplatform.com', '.logic.azure.com')" in forms
    assert 'legacy Office 365 connector webhook URLs' in page
    assert 'name="teams_workflow_url" type="password"' in page
    assert 'form_channel.teams_workflow_url' not in page


def test_notification_channels_redesign_surfaces_delivery_governance():
    page = read('app/templates/integrations/notification_channels/index.html')
    for label in ('Delivery Providers', 'Channel Configuration', 'Configured Channels', 'Delivery Contract', 'Delivery Ownership'):
        assert label in page
    for provider in ('Telegram', 'Email', 'Microsoft Teams'):
        assert provider in page
    assert 'platform integration capability' in page.lower()
    forms = read('app/notification_channels/forms.py')
    assert "'report.generated'" in forms
    assert "'automation.approval_required'" in forms
    assert "'automation.decision_approved'" in forms
    assert "'automation.decision_rejected'" in forms
    assert "'automation.execution_failed'" in forms
