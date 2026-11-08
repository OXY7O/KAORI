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
    assert "if any(key.startswith('object_storage.') for key in rules):" in service
    assert "collect('Object Storage', build_object_storage_recommendation_findings)" in service
    assert 'findings.extend(evaluator(rules))' in service
    assert 'except SQLAlchemyError:' in service
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
    assert (
        'selected_cluster_id: str | None = None'
        not in service[service.index('def get_active_recommendation_findings(') :]
    )
    assert 'domain: str | None = None' in service
    assert 'asset_key: str | None = None' in service


def test_object_storage_recommendation_thresholds_match_analytics_capacity_boundaries():
    evaluator = read('app/intelligence/object_storage_recommendations.py')
    capacity = read('app/storage/object_storage/analytics/presentation.py')

    assert 'QUOTA_WARNING_PERCENT = 85.0' in evaluator
    assert 'QUOTA_CRITICAL_PERCENT = 95.0' in evaluator
    assert "row['quota_utilization'] >= 85" in capacity
    assert "row['quota_utilization'] >= 95" in capacity


def test_storage_and_registry_dashboard_copy_is_rule_authored() -> None:
    import yaml

    catalog = yaml.safe_load(read('app/definitions/catalogs/intelligence/rules.yaml'))
    selected = {rule['rule_key']: rule for rule in catalog['rules'] if rule['domain'] in {'object_storage', 'registry'}}
    assert len(selected) == 18
    assert sum(rule['domain'] == 'object_storage' for rule in selected.values()) == 12
    assert sum(rule['domain'] == 'registry' for rule in selected.values()) == 6
    for rule in selected.values():
        action = rule['dashboard_action']
        assert 35 <= len(action) <= 110
        assert action.endswith('.')
        assert rule['recommended_action'] != action
        assert action not in rule['recommended_action']

    encryption = selected['object_storage.bucket.encryption_not_configured']
    assert encryption['dashboard_action'] == (
        'Check data classification. Apply approved encryption if required; resync inventory.'
    )
    vulnerability = selected['registry.security.critical_runtime_vulnerability']
    assert vulnerability['dashboard_action'] == (
        'Validate exposure and fixed-artifact options. Use approved deployment controls.'
    )
    correlation = selected['registry.runtime.tag_only_correlation']
    assert correlation['dashboard_action'] == (
        'Use pinned digests or verified imageID evidence. Refresh Registry correlation.'
    )


def test_dashboard_projection_prefers_authored_action_without_losing_finding_identity(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from app.artifact_registry import presentation_common as registry
    from app.storage.object_storage.dashboard import service as storage

    findings = [
        {
            'title': 'Finding with compact action',
            'rule_key': 'domain.rule:asset',
            'recommended_action': 'Full remediation instructions stay in Intelligence.',
            'dashboard_action': 'Review evidence. Prepare a governed change.',
            'category': 'governance',
            'priority': 'P2',
            'severity': 'warning',
            'signal_source': 'object_storage_inventory',
        },
        {
            'title': 'Unmapped legacy finding',
            'rule_key': 'domain.other:asset',
            'recommended_action': 'Keep complete guidance when short copy is absent.',
        },
    ]
    for module, builder in (
        (storage, storage._recommended_actions),
        (registry, registry._registry_recommended_actions),
    ):
        calls = []

        def findings_stub(*, domain, asset_key):
            calls.append((domain, asset_key))
            return findings

        monkeypatch.setattr(module, 'get_dashboard_recommendation_findings', findings_stub)
        cards = builder(SimpleNamespace(id=17))
        assert calls == [('object_storage' if module is storage else 'registry', '17')]
        assert cards[0]['description'] == findings[0]['dashboard_action']
        assert cards[1]['description'] == findings[1]['recommended_action']
        for field in ('title', 'rule_key', 'priority', 'severity'):
            assert cards[0][field] == findings[0][field]
        assert findings[0]['recommended_action'] == ('Full remediation instructions stay in Intelligence.')


def test_shared_recommendation_card_and_kubernetes_copy_stay_unchanged() -> None:
    cards = read('app/templates/components/operational_recommendation_cards.html')
    kubernetes = read('app/kubernetes/dashboard/sections/recommendations.py')
    catalog = read('app/intelligence/catalog.py')
    assert '{{ action.description }}' in cards
    assert 'line-clamp-2 break-words text-sm font-semibold' in cards
    assert 'mt-2 line-clamp-2 text-xs leading-5 text-content-muted' in cards
    assert "card.get('recommended_action')" in kubernetes
    assert "card.get('dashboard_action')" not in kubernetes
    assert "require_str(raw, 'dashboard_action', path)" in catalog
