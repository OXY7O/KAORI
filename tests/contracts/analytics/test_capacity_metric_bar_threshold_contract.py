from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_capacity_allocation_items_own_resolved_tones_and_missing_evidence() -> None:
    domain = read('app/analytics/capacity/domain.py')
    template = read('app/templates/analytics/capacity/partials/_allocation.html')

    assert "'tone': tone if available else 'unknown'" in domain
    assert "'available': available" in domain
    assert "allocation_item['percent']" in template
    assert "allocation_item['available']" in template
    assert "semantic_bar(allocation_item['percent'], section_status" not in template


def test_capacity_domain_preserves_initialisms_and_distinct_pressure_thresholds() -> None:
    domain = read('app/analytics/capacity/domain.py')

    assert "'cpu': 'CPU'" in domain
    assert "'Remaining Pod Slots'" in domain
    assert 'allocation_pressure_tone(raw_value or 0)' in domain
    assert 'allocation_headroom_tone(raw_value or 0)' in domain
    assert "'CPU Request Overcommit'" not in domain  # label is built through the canonical resource label.
    assert "f'{resource_display_label(resource)} Request Overcommit'" in domain
    assert "f'{resource_display_label(resource)} Limit Overcommit'" in domain


def test_capacity_templates_use_backend_status_and_semantic_progress() -> None:
    allocation = read('app/templates/analytics/capacity/partials/_allocation.html')
    risk = read('app/templates/analytics/capacity/partials/_risk.html')

    assert "section['status']" in allocation
    assert 'progress_bar.pressure_tone' not in allocation
    assert 'progress_bar.headroom_tone' not in allocation
    assert "progress_bar.semantic_bar(allocation_item['percent'], allocation_item['tone']" in allocation
    assert 'item.label' in risk
    assert 'progress_bar.semantic_bar(item.headroom, tone' in risk


def test_capacity_pod_profile_has_no_duplicate_usage_row() -> None:
    domain = read('app/analytics/capacity/domain.py')
    allocation = read('app/templates/analytics/capacity/partials/_allocation.html')

    assert "_allocation_item('Current Pods'" in domain
    assert "'Remaining Pod Slots'" in domain
    assert "'Pod Usage'" not in domain
    assert 'Pod Usage' not in allocation
