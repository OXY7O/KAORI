"""Coverage display is not an admission or provider-read capability (#5230)."""

from app.intelligence.alert_intelligence.provider_case_scope import registered_provider_case_adapters
from app.intelligence.alert_intelligence.provider_coverage import provider_coverage_rows


def test_coverage_tracks_seven_explicit_provider_contracts_without_runtime_claims():
    rows = provider_coverage_rows()
    assert [(row['domain'], row['provider']) for row in rows] == [
        ('Kubernetes', 'Kubernetes'),
        ('Object Storage', 'MinIO'),
        ('Artifact Registry', 'Harbor'),
        ('Secrets & PKI', 'Vault'),
        ('Secrets & PKI', 'OpenBao'),
        ('Source Control', 'GitHub'),
        ('Infrastructure Automation', 'Ansible'),
    ]
    assert [row['origin'] for row in rows] == [
        'Recommendation', 'Recommendation', 'Recommendation', 'Provider alert',
        'Not admitted', 'Not admitted', 'Not admitted',
    ]
    assert all('available' not in row['status'].lower() for row in rows)
    assert all(set(row) == {'domain', 'provider', 'origin', 'status', 'tone', 'limitation'} for row in rows)


def test_only_registered_vault_adapter_is_described_as_scoped_read():
    registered = registered_provider_case_adapters()
    assert registered == frozenset({('secrets_pki', 'vault')})
    rows = provider_coverage_rows()
    assert [row['provider'] for row in rows if row['status'] == 'Scoped read registered'] == ['Vault']
    assert all(row['status'] == 'Not qualified' for row in rows[4:])


def test_coverage_output_cannot_mutate_authoritative_registry():
    first = provider_coverage_rows()
    first[3]['status'] = 'Qualified in production'
    assert provider_coverage_rows()[3]['status'] == 'Scoped read registered'
