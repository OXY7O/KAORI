"""Regression guards for the shared Integration Title Case visible-label parser."""

from pathlib import Path

from scripts.verify_integrations_title_case import _VisibleLabelParser, _title_case_error

ROOT = Path(__file__).resolve().parents[3]


def test_vault_stored_pki_checkbox_title_excludes_descriptive_help() -> None:
    source = (ROOT / 'app/templates/integrations/secrets_management/vault/form.html').read_text(encoding='utf-8')
    parser = _VisibleLabelParser()
    parser.feed(source)

    labels = [text for _, text in parser.labels]
    title = 'Enable Stored PKI Certificate Collection (Explicit Opt-In)'
    assert title in labels
    assert _title_case_error(title) is None
    assert 'Enable This Connection' in labels
    assert all('Adds optional authenticated LIST /certs reads' not in label for label in labels)


def test_ignored_help_does_not_exempt_invalid_checkbox_title() -> None:
    parser = _VisibleLabelParser()
    parser.feed(
        '<label><span><span class="font-semibold">Enable bad Checkbox</span>'
        '<span class="mt-1 block text-xs text-content-muted">'
        'This prose can include lowercase words.</span></span></label>'
    )

    labels = [text for _, text in parser.labels]
    assert labels == ['Enable bad Checkbox']
    assert _title_case_error(labels[0]) is not None


def test_non_help_label_content_and_technical_version_still_checked() -> None:
    parser = _VisibleLabelParser()
    parser.feed('<label><span class="text-xs text-content-muted">Enable bad Connection</span></label>')

    labels = [text for _, text in parser.labels]
    assert labels == ['Enable bad Connection']
    assert _title_case_error(labels[0]) is not None
    assert _title_case_error('KV v2 Inventory Evidence') is None
