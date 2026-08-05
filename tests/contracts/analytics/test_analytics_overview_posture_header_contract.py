from pathlib import Path


def test_overview_posture_header_does_not_duplicate_status_value() -> None:
    template = Path('app/templates/analytics/overview/partials/_hero_posture.html').read_text()

    assert 'page_hero.context_card_body(' in template
    assert "'Operational Posture'" in template
    assert "'Analytics Status'" in template
    assert '{{ posture.value }}' not in template
    assert template.count("'Actionable'") == 1
    assert template.count("'Active Alerts'") == 1
    assert 'Manage Clusters' in template
