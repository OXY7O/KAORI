from pathlib import Path


def test_catalog_exception_history_is_sql_bounded() -> None:
    src = Path('app/intelligence/rule_exceptions.py').read_text(encoding='utf-8')
    assert 'active_count = active_query.count()' in src
    assert 'active_query.filter(RuleException.expires_at <= current + _EXPIRING_WINDOW).count()' in src
    assert 'active_query.filter(RuleException.asset_key.in_(asset_keys)).all()' in src
    assert '.limit(12)' in src
    assert 'for row in rows[:12]' not in src
    assert 'if include_owner_options and asset_rows else []' in src


def test_catalog_detail_disables_exception_create_when_evidence_partial() -> None:
    detail = Path('app/templates/intelligence/partials/_catalog_detail_content.html').read_text(encoding='utf-8')
    assert 'role="alert"' in detail
    assert "not item.rule_exceptions.evaluation_issues" in detail
