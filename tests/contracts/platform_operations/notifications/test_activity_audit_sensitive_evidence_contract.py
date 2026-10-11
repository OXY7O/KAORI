from __future__ import annotations

from app.platform_operations.notifications.metadata import (
    changed_fields,
    metadata_items,
    redact_operational_metadata,
    redact_operational_text,
)


def test_nested_dict_and_list_redaction_preserves_safe_references() -> None:
    raw = {
        'secret_name': 'k8s-tls-prod',
        'credential_id': 'cred-123',
        'runbook': {
            'pod': 'nginx-0',
            'clientSecret': 'synthetic-hidden-credential',
            'steps': [{'refresh_token': 'synthetic-hidden-token'}, {'reason': 'approved'}],
        },
        'request': [{'Authorization': 'synthetic-hidden-header'}, {'error': 'token=synthetic-hidden-inline'}],
    }
    clean = redact_operational_metadata(raw)
    assert clean is not None
    assert clean['secret_name'] == 'k8s-tls-prod'
    assert clean['credential_id'] == 'cred-123'
    assert clean['runbook']['pod'] == 'nginx-0'
    assert 'clientSecret' not in clean['runbook']
    assert 'refresh_token' not in clean['runbook']['steps'][0]
    assert clean['runbook']['steps'][1] == {'reason': 'approved'}
    assert 'Authorization' not in clean['request'][0]
    assert 'synthetic-hidden-inline' not in clean['request'][1]['error']
    assert raw['runbook']['clientSecret'] == 'synthetic-hidden-credential'  # no input mutation


def test_technical_text_scrubber_handles_encoded_keys_urls_headers_and_controls() -> None:
    cases = (
        'endpoint=https://viewer:synthetic-hidden-pass@example.test/path',
        'Authorization: Bearer synthetic-hidden-bearer.value',
        'token=synthetic-hidden-token',
        'api_key%3Dsynthetic-hidden-encoded',
        'secret%253Dsynthetic-hidden-double-encoded',
        'password: synthetic-hidden-password',
        'token: "synthetic-hidden-multi word value"',
        "client_secret: 'synthetic-hidden-space separated'",
        'private_key=synthetic-hidden-private',
        'cookie=synthetic-hidden-cookie',
        'x-api-key=synthetic-hidden-api',
        'client-secret=synthetic-hidden-client',
        'failed\nrequest token=synthetic-hidden-other',
    )
    for raw in cases:
        assert 'synthetic-hidden-' not in redact_operational_text(raw)
    assert redact_operational_text('-----BEGIN PRIVATE KEY----- synthetic-hidden-material') == '[REDACTED]'
    assert redact_operational_text('Success: task_id=111, target=cluster-a') == 'Success: task_id=111, target=cluster-a'
    assert redact_operational_text('/audit?redirect=%2Faccess%2Factivity') == '/audit?redirect=%2Faccess%2Factivity'
    assert len(redact_operational_text('x' * 20000, limit=1200)) <= 1200


def test_recursive_scrubbing_is_applied_to_detail_metadata_and_changed_fields() -> None:
    evidence = {
        'operation': [{'secret_value': 'synthetic-hidden-a'}, {'message': 'token=synthetic-hidden-b'}],
        'previous_configuration': {'password': 'synthetic-hidden-c', 'enabled': False},
        'configuration': {'enabled': True, 'client_secret': 'synthetic-hidden-d'},
        'job_execution_id': 124,
    }
    items = metadata_items(evidence, event_type='integration_runtime_refresh')
    represented = ' '.join(str(item['value']) for item in items)
    assert 'synthetic-hidden-' not in represented
    assert any(item['key'] == 'job_execution_id' for item in items)
    changes = changed_fields(evidence)
    assert len(changes) == 1
    assert changes[0]['label'] == 'Configuration'
    assert 'synthetic-hidden-' not in str(changes)


def test_sensitive_suffix_bypass_not_permitted_except_known_identifier_keys() -> None:
    raw = {
        'password_ref': 'synthetic-hidden-mislabeled',
        'OAuthTokenName': 'synthetic-hidden-bypass',
        'secret_ref': 'vault-path-042',
        'token_id': 'token-record-14',
        'credential_value_id': 'synthetic-hidden-invalid',
    }
    clean = redact_operational_metadata(raw)
    assert clean is not None
    assert 'password_ref' not in clean
    assert 'OAuthTokenName' not in clean
    assert 'credential_value_id' not in clean
    assert clean['secret_ref'] == 'vault-path-042'
    assert clean['token_id'] == 'token-record-14'


def test_sanitizer_bounds_oversized_nested_evidence() -> None:
    very_deep = {'nested': {'password': 'synthetic-hidden'}}
    for _ in range(20):
        very_deep = {'nested': very_deep}
    cleaned = redact_operational_metadata(very_deep)
    assert cleaned is not None
    assert 'synthetic-hidden' not in str(cleaned)
    assert redact_operational_metadata({'values': list(range(1000))})['values'] == list(range(500))
