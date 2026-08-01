from pathlib import Path


def test_record_pagination_uses_canonical_footer():
    template = Path('app/templates/analytics/components/_record_pagination.html').read_text()
    assert '>Rows</label>' in template
    assert 'Scope Contains' not in template
    assert 'Filtered Namespaces' not in template
    assert 'Filtered Workloads' not in template
