from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_object_storage_rule_catalog_is_domain_owned_and_minio_covered():
    catalog = read('app/intelligence/catalog.py')

    assert catalog.count("'domain': 'object_storage'") >= 12
    assert catalog.count("'provider_keys': ['minio']") >= 12
    assert "'rule_key': 'minio." not in catalog
    assert "'rule_key': 'object_storage." in catalog


def test_object_storage_metric_signal_catalog_matches_analytics_boundaries():
    catalog = read('app/intelligence/catalog.py')
    analysis = read('app/analytics/object_storage/analysis.py')

    for rule_key in (
        'object_storage.metric.capacity_pressure',
        'object_storage.metric.capacity_critical',
        'object_storage.metric.request_error_pressure',
        'object_storage.metric.request_error_critical',
        'object_storage.metric.requests_waiting',
        'object_storage.metric.offline_nodes',
    ):
        assert f"'rule_key': '{rule_key}'" in catalog

    assert 'CAPACITY_WARNING_PERCENT = 85.0' in analysis
    assert 'CAPACITY_CRITICAL_PERCENT = 95.0' in analysis
    assert 'ERROR_WARNING_PERCENT = 5.0' in analysis
    assert 'ERROR_CRITICAL_PERCENT = 10.0' in analysis
    assert "at least 85% and below 95%" in catalog
    assert "at least 95%" in catalog
    assert "at least 5% and below 10%" in catalog
    assert "at least 10%" in catalog
    assert "greater than zero" in catalog


def test_rule_catalog_uses_generic_evidence_boundary_and_provider_coverage():
    catalog = read('app/intelligence/catalog.py')
    service = read('app/intelligence/service.py')
    presentation = read('app/intelligence/rule_presentation.py')
    page = read('app/templates/intelligence/rule_catalog.html')
    filters = read('app/templates/intelligence/partials/_filters.html')
    records = read('app/templates/intelligence/partials/_catalog_records.html')
    details = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert 'prometheus_relationship' not in catalog
    assert 'prometheus_relationship' not in service
    assert 'item.prometheus_relationship' not in details
    assert "'evidence_boundary'" in catalog
    assert 'item.evidence_boundary' in details

    assert "'provider': clean(args.get('provider'))" in service
    assert "'providers': PROVIDER_OPTIONS" in service
    assert "{'value': 'minio', 'label': 'MinIO'}" in presentation
    assert "selected_provider not in provider_keys(rule)" in presentation
    assert 'Provider Coverage' in filters
    assert 'item.provider_label' in records
    assert "intelligence_ui.field('Provider Coverage', item.provider_label)" in details

    assert 'payload.summary.domains' in page
    assert 'payload.summary.minio' in page
    assert '3 Asset Domains' not in page


def test_rule_catalog_provider_filter_matches_current_coverage_without_provider_rule_namespace():
    presentation = read('app/intelligence/rule_presentation.py')
    standard = read('docs/design/components/INTELLIGENCE_WORKSPACE_STANDARD.md')

    assert "{'value': 'minio', 'label': 'MinIO'}" in presentation
    assert "selected_provider not in provider_keys(rule)" in presentation
    assert 'Provider coverage is implementation evidence' in standard
    assert 'must not change the canonical rule namespace' in standard
