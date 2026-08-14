from pathlib import Path


def test_record_collections_use_bracket_access_for_items_key():
    recommendations = Path('app/templates/intelligence/partials/_recommendation_records.html').read_text()
    catalog = Path('app/templates/intelligence/partials/_catalog_records.html').read_text()
    overview = Path('app/templates/intelligence/partials/automation_control/_overview.html').read_text()

    assert "payload['items']|default([], true)" in recommendations
    assert "payload['items']|default([], true)" in catalog

    assert 'payload.items' not in recommendations
    assert 'payload.items' not in catalog
    assert 'domain_groups' not in overview
    assert 'group.items' not in overview


def test_intelligence_record_templates_do_not_reintroduce_ambiguous_items_access():
    paths = [
        Path('app/templates/intelligence/partials/_recommendation_records.html'),
        Path('app/templates/intelligence/partials/_catalog_records.html'),
        Path('app/templates/intelligence/partials/automation_control/_overview.html'),
    ]
    content = '\n'.join(path.read_text() for path in paths)
    assert '.items %}' not in content
    assert '.items|length' not in content
