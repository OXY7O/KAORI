"""Coverage is a read model: persisted Ready never overrides source lifecycle."""

from types import SimpleNamespace

import pytest

from app.integrations.coverage import _coverage_source_options, _coverage_status


def _source(*, enabled=True, canonical_enabled=True, lifecycle='active', readiness='ready'):
    canonical = SimpleNamespace(enabled=canonical_enabled, lifecycle_status=lifecycle)
    return SimpleNamespace(
        enabled=enabled,
        integration_instance=canonical,
        readiness_status=readiness,
        integration_instance_id=17,
        id=4,
        name='prometheus',
        endpoint_product='Prometheus',
    )


def _status(source, *, binding_enabled=True, binding_status='ready'):
    binding = SimpleNamespace(
        enabled=binding_enabled,
        validation_status=binding_status,
        validation_message=None,
    )
    return _coverage_status(
        selected_binding=binding,
        selected_source=source,
        shared=False,
        selector_configured=True,
    )


@pytest.mark.parametrize(
    ('provider_enabled', 'canonical_enabled', 'lifecycle', 'expected'),
    [
        (True, True, 'active', 'ready'),
        (False, True, 'active', 'blocked'),
        (True, False, 'active', 'blocked'),
        (True, True, 'disabled', 'blocked'),
        (True, True, 'deleting', 'blocked'),
    ],
)
def test_source_lifecycle_prevents_false_ready(provider_enabled, canonical_enabled, lifecycle, expected):
    source = _source(
        enabled=provider_enabled,
        canonical_enabled=canonical_enabled,
        lifecycle=lifecycle,
    )
    status, label, _detail = _status(source)
    assert status == expected
    if expected == 'blocked':
        assert label in ('Source Disabled', 'Source Inactive')


def test_binding_validation_still_distinguishes_consumer_from_provider() -> None:
    assert _status(_source(), binding_status='validation_required')[0] == 'validation_required'
    assert _status(_source(readiness='degraded'))[0] == 'degraded'
    assert (
        _coverage_status(selected_binding=None, selected_source=None, shared=False, selector_configured=False)[0]
        == 'uncovered'
    )


def test_disabled_and_inactive_sources_are_not_selectable() -> None:
    instances = [_source(), _source(enabled=False), _source(lifecycle='deleting')]
    options = _coverage_source_options(
        instances,
        meta={'label': 'Metrics'},
        sharing_counts={},
        unscoped_counts={},
    )
    assert len(options) == 1
    assert options[0]['selectable'] is True
