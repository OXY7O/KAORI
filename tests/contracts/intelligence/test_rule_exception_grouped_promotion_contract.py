from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_rule_exception_has_durable_model_and_migration_contract():
    model = read('app/models/alert_ops.py')
    migration = read('migrations/versions/20260823_rule_exception_grouping.py')

    assert 'class RuleException(db.Model)' in model
    assert "__tablename__ = 'rule_exceptions'" in model
    assert "scope_mode IN ('rule_asset', 'finding_keys')" in model
    assert 'finding_keys_json' in model
    assert 'expires_at' in model
    assert 'revoked_at' in model
    assert 'rule_exception_id' in model
    assert "'accepted_risk'" in model
    assert "'superseded'" in model

    assert "revision = '20260823_rule_exceptions'" in migration
    assert "down_revision = '20260823_alert_signal_eval'" in migration
    assert "op.create_table(\n        'rule_exceptions'" in migration
    assert "'recommendation_alert_states'" in migration
    assert "'rule_exception_id'" in migration


def test_accepted_risk_suppresses_promotion_without_hiding_findings():
    matcher = read('app/intelligence/rule_exceptions.py')
    alerting = read('app/intelligence/recommendation_alerting.py')
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')

    assert 'def matching_rule_exception(' in matcher
    assert "row.scope_mode == 'rule_asset'" in matcher
    assert "row.scope_mode == 'finding_keys'" in matcher
    assert "status = 'exception_active'" in alerting
    assert "label = 'Accepted Risk'" in alerting
    assert "{'value': 'accepted_risk', 'label': 'Accepted Risk'}" in read('app/intelligence/service.py')
    assert 'active_exceptions = active_rule_exceptions(' in source
    assert 'matching_rule_exception(finding, rows=active_exceptions, now=now)' in source
    assert "stats['accepted_risk'] += 1" in source
    assert 'state.rule_exception_id = exception.id' in source
    assert 'close_accepted_risk_alert(' in source
    assert 'already overlaps this rule and asset scope' in matcher


def test_grouped_promotion_uses_rule_asset_and_preserves_child_evidence():
    rules = read('app/definitions/catalogs/intelligence/rules.yaml')
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')
    service = read('app/intelligence/alert_intelligence/service.py')

    encryption_block = rules.split('- rule_key: object_storage.bucket.encryption_not_configured', 1)[1].split(
        '- rule_key:', 1
    )[0]
    assert 'grouping_mode: rule_asset' in encryption_block
    assert "if grouping_mode == 'rule_asset':" in source
    assert "'object_storage': 'object_storage_system'" in source
    assert "raw = '|'.join((rule_key, asset_key))" in source
    assert "'recommendation_sources': sources" in source
    assert "'recommendation_count': len(sources)" in source
    assert "'affected_preview': targets[:5]" in source
    assert 'def _rehome_state_for_grouping(' in source
    assert 'supersede_recommendation_alert(' in source
    assert "'accepted_risk_count', 'Accepted Risk Findings'" in service
    assert "return 'Suppressed · Accepted Risk'" in service
    assert 'def _remove_accepted_risk_source(' in source
    assert "evidence['affected_preview'] = []" in source


def test_rule_catalog_exposes_exception_registry_and_governed_mutations():
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    catalog_rows = read('app/templates/intelligence/partials/_catalog_records.html')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    commands = read('app/intelligence/recommendation_alert_commands.py')

    for token in (
        'Risk Exceptions',
        'Active Exceptions',
        'Covered Findings',
        'Actionable Findings',
        'Create Accepted Risk',
        'Entire Asset',
        'Selected Findings',
        'Expires In',
        'Risk / Change Reference',
        'Revoke Exception',
    ):
        assert token in detail
    assert 'item.active_exception_count' in catalog_rows
    assert "@alert_intelligence_bp.post('/rule-exceptions/<path:rule_key>')" in routes
    assert "@alert_intelligence_bp.post('/rule-exceptions/<string:exception_public_id>/revoke')" in routes
    assert 'def create_rule_exception_command(' in commands
    assert 'def revoke_rule_exception_command(' in commands
    assert 'apply_rule_exception_to_active_findings' in commands


def test_recommendation_and_telegram_surface_grouped_exception_context():
    detail = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    records = read('app/templates/intelligence/partials/_recommendation_records.html')
    templates = read('app/intelligence/alert_intelligence/templates.py')

    assert "item.alert_handling.status == 'exception_active'" in detail
    assert 'Accepted Risk Active' in detail
    assert 'Detection retained · promotion suppressed' in records
    assert '📦 <b>Affected</b>' in templates
    assert "'affected_summary': affected_summary" in templates
