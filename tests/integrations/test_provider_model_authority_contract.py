from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_provider_tables_only_store_provider_specific_fields():
    prometheus = (ROOT / 'app/models/prometheus.py').read_text(encoding='utf-8')
    alertmanager = (ROOT / 'app/models/alertmanager.py').read_text(encoding='utf-8')

    forbidden_columns = (
        "mapped_column(String(160), nullable=False, unique=True)",
        "readiness_status: Mapped",
        "last_status: Mapped",
        "last_error: Mapped",
        "last_checked_at: Mapped",
    )
    for source in (prometheus, alertmanager):
        for forbidden in forbidden_columns:
            assert forbidden not in source


def test_shared_provider_fields_delegate_to_integration_instance():
    for relative in ('app/models/prometheus.py', 'app/models/alertmanager.py'):
        source = (ROOT / relative).read_text(encoding='utf-8')
        assert "association_proxy(" in source
        assert "'integration_instance'," in source
        assert "'readiness_status'," in source
        assert "'health_status'," in source
        assert "'last_error'," in source
        assert "'last_checked_at'," in source


def test_lifecycle_does_not_mirror_shared_fields():
    source = (ROOT / 'app/integrations/lifecycle.py').read_text(encoding='utf-8')
    assert "canonical.name = provider_record.name" not in source
    assert "canonical.enabled =" not in source
    assert "canonical.readiness_status =" not in source
    assert "canonical.last_error =" not in source
    assert "canonical.last_checked_at =" not in source


def test_provider_queries_use_canonical_identity():
    alertmanager = (ROOT / 'app/alertmanager/repository.py').read_text(encoding='utf-8')
    prometheus = (ROOT / 'app/prometheus/service.py').read_text(encoding='utf-8')
    integrations = (ROOT / 'app/integrations/service.py').read_text(encoding='utf-8')

    assert 'IntegrationInstance.name.asc()' in alertmanager
    assert "IntegrationInstance.name == name" in alertmanager
    assert "IntegrationInstance.name == (form.name.data or '').strip()" in prometheus
    assert 'PrometheusInstance.name.asc()' not in integrations
    assert 'AlertmanagerInstance.name.asc()' not in integrations
