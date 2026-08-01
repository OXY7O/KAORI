from pathlib import Path


def test_overview_posture_header_does_not_duplicate_status_value():
    template = Path('app/templates/analytics/overview/partials/_hero_posture.html').read_text()
    assert '>Operational Posture</h2>' in template
    assert '{{ posture.value }}' not in template
    assert 'table_label.status_label(' in template
    assert template.count('Actionable') == 1
    assert template.count('Active Alerts') == 1
    assert 'Manage Clusters' in template
