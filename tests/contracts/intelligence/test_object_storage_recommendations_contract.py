from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_recommendations_support_object_storage_without_minio_specific_workspace():
    service = read('app/intelligence/service.py')
    presentation = read('app/intelligence/rule_presentation.py')
    evaluator = read('app/intelligence/object_storage_recommendations.py')
    template = read('app/templates/intelligence/recommendations.html')

    assert "{'value': 'object_storage', 'label': 'Object Storage'}" in presentation
    assert "{'value': 'object_storage_bucket', 'label': 'Object Storage Bucket'}" in presentation
    assert "{'value': 'object_storage_inventory', 'label': 'Object Storage Inventory'}" in presentation
    assert 'build_object_storage_recommendation_findings(rules)' in service
    assert 'ObjectStorageSystem.query.options(' in evaluator
    assert 'ObjectStorageForecastSnapshot.query.filter_by(' in evaluator
    assert "provider_key != 'minio'" in evaluator
    assert 'Prometheus' not in '\n'.join(
        line for line in evaluator.splitlines() if line.startswith('from ') or line.startswith('import ')
    )
    assert 'Alertmanager' not in '\n'.join(
        line for line in evaluator.splitlines() if line.startswith('from ') or line.startswith('import ')
    )
    assert 'payload.scope_label' in template
    assert "page_hero.meta_label('boxes', 'Kubernetes')" not in template


def test_object_storage_recommendations_are_catalog_backed_and_provider_evidenced():
    catalog = read('app/definitions/catalogs/intelligence/rules.yaml')
    evaluator = read('app/intelligence/object_storage_recommendations.py')
    records = read('app/templates/intelligence/partials/_recommendation_records.html')
    details = read('app/templates/intelligence/partials/_recommendation_detail_content.html')

    for rule_key in (
        'object_storage.bucket.quota_pressure',
        'object_storage.bucket.quota_critical',
        'object_storage.bucket.public_exposure',
        'object_storage.bucket.encryption_not_configured',
        'object_storage.forecast.capacity_exhaustion_review',
        'object_storage.forecast.capacity_exhaustion_critical',
    ):
        assert f'rule_key: {rule_key}' in catalog

    assert 'domain: object_storage' in catalog
    assert "'provider_label': provider_label" in evaluator
    assert 'item.evidence.provider_label' in records
    assert 'item.evidence.provider_label' in details


def test_kubernetes_dashboard_scopes_central_recommendations_explicitly():
    engine = read('app/intelligence/recommendation_engine.py')
    service = read('app/intelligence/service.py')

    assert "domain='kubernetes'" in engine
    assert 'asset_key=selected_cluster_id' in engine
    assert 'selected_cluster_id: str | None = None' not in service[service.index('def get_active_recommendation_findings('):]
    assert 'domain: str | None = None' in service
    assert 'asset_key: str | None = None' in service


def test_object_storage_recommendation_thresholds_match_analytics_capacity_boundaries():
    evaluator = read('app/intelligence/object_storage_recommendations.py')
    capacity = read('app/analytics/object_storage/presentation.py')

    assert 'QUOTA_WARNING_PERCENT = 85.0' in evaluator
    assert 'QUOTA_CRITICAL_PERCENT = 95.0' in evaluator
    assert "row['quota_utilization'] >= 85" in capacity
    assert "row['quota_utilization'] >= 95" in capacity
