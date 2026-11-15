"""Shared provider configuration contract: editable and source-immutable variants.

The Ansible source registration is intentionally immutable. Other Integration
providers continue to use the normal Configure Connection link and default copy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import render_template_string

from app import create_app

ROOT = Path(__file__).resolve().parents[3]


_TEMPLATE = """
{% import 'integrations/components/_provider_configuration_contract.html' as contract %}
{{ contract.render(
    'Example',
    'workflow',
    'validation_required',
    [('Canonical Identity', 'example-01', 'Canonical KAORI identity')],
    [('git-commit', 'brand', 'Git Commit SHA', 'a' * 40, 'Immutable source evidence')],
    'External execution remains provider-owned.',
    [('Register', 'Track a reviewed source.', 'git-commit')],
    'Reviewed configuration evidence only.',
    configure_url,
    contract_description=contract_copy,
    evidence_description=evidence_copy,
    read_only_label='Immutable Source',
    monospace_evidence_labels=('Git Commit SHA',)
) }}
"""


def _render(*, configure_url: str | None, contract_copy: str | None = None, evidence_copy: str | None = None) -> str:
    app = create_app('testing')
    with app.test_request_context('/integrations/ansible/connections/1'):
        return render_template_string(
            _TEMPLATE,
            configure_url=configure_url,
            contract_copy=contract_copy,
            evidence_copy=evidence_copy,
        )


def test_provider_editable_configuration_keeps_existing_link_and_default_copy() -> None:
    result = _render(configure_url='/integrations/example/edit')
    assert 'data-kaori-provider-configuration-contract' in result
    assert 'href="/integrations/example/edit"' in result
    assert 'Configure Connection' in result
    assert 'data-kaori-provider-immutable-connection' not in result
    assert 'Canonical identity, endpoint trust, access boundaries' in result
    assert 'Effective endpoint, transport trust, credential mode' in result
    assert 'Open guide: Example Connection Contract' in result


def test_source_only_configuration_uses_same_contract_without_fake_edit_action() -> None:
    result = _render(
        configure_url=None,
        contract_copy='Immutable reviewed Git source; no credentials requested.',
        evidence_copy='Committed Git tree and version policy only.',
    )
    assert result.count('data-kaori-provider-configuration-contract') == 1
    assert 'data-kaori-provider-operational-context' in result
    assert 'data-kaori-provider-immutable-connection' in result
    assert 'Immutable Source' in result
    assert 'Configure Connection' not in result
    assert 'href="None"' not in result
    assert 'Immutable reviewed Git source; no credentials requested.' in result
    assert 'Committed Git tree and version policy only.' in result
    assert 'font-mono text-xs break-all' in result


@pytest.mark.parametrize(
    'provider_template',
    [
        'integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html',
        'integrations/secrets_management/vault/partials/_detail_configuration.html',
        'integrations/registry/providers/harbor/partials/_detail_configuration.html',
        'integrations/observability/metrics_source/partials/_detail_configuration.html',
        'integrations/observability/alert_source/providers/alertmanager/partials/_detail_configuration.html',
    ],
)
def test_existing_editable_providers_retain_canonical_configure_route(provider_template: str) -> None:
    template = (ROOT / 'app/templates' / provider_template).read_text()
    assert 'provider_configuration_contract.render(' in template
    assert 'url_for(' in template
    assert 'configure_url=none' not in template
