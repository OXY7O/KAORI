from pathlib import Path


def test_capacity_allocation_bars_use_item_tones():
    template = Path('app/templates/analytics/capacity/partials/_allocation.html').read_text()
    assert "allocation_item['tone']" in template
    assert "semantic_bar(allocation_item['percent'], section_status" not in template


def test_capacity_service_preserves_initialism_and_metric_thresholds():
    source = Path('app/analytics/capacity/service.py').read_text()
    assert "'cpu': 'CPU'" in source
    assert "'tone': tone or allocation_pressure_tone(percent)" in source
    assert "'Remaining Pod Slots'" in source and 'allocation_headroom_tone' in source


def test_capacity_templates_support_existing_snapshots_and_uppercase_cpu():
    allocation = Path('app/templates/analytics/capacity/partials/_allocation.html').read_text()
    risk = Path('app/templates/analytics/capacity/partials/_risk.html').read_text()
    assert "progress_bar.pressure_tone(item_percent)" in allocation
    assert "progress_bar.headroom_tone(item_percent)" in allocation
    assert "'CPU' if item.resource" in risk
