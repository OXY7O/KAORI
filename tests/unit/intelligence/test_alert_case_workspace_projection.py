from __future__ import annotations

from types import SimpleNamespace

from app.intelligence.alert_intelligence import service


def test_source_unknown_filter_is_independent_of_severity() -> None:
    cases = [
        SimpleNamespace(
            severity='critical', workflow_state='open',
            source_type='recommendation', source_state='unknown',
        ),
        SimpleNamespace(
            severity='warning', workflow_state='open',
            source_type='recommendation', source_state='firing',
        ),
    ]
    matching = service._filter_cases(
        cases, severity='all', workflow='all',
        source_type='all', source_state='unknown', search='',
    )
    assert matching == [cases[0]]
    assert service._filter_cases(
        cases, severity='critical', workflow='all',
        source_type='all', source_state='unknown', search='',
    ) == [cases[0]]


def test_missing_registry_scope_does_not_claim_snapshot_available() -> None:
    snapshot = service._snapshot_context(
        domain='registry', asset_key=service._INVALID_REGISTRY_SCOPE,
    )
    assert snapshot['available'] is False
    assert snapshot['serving_last_good'] is True


def test_scoped_counts_do_not_equate_unknown_source_with_critical_firing() -> None:
    active = [
        SimpleNamespace(
            severity='critical', workflow_state='open',
            source_state='unknown',
        ),
    ]
    counts = service._case_counts_from_rows(active, [])
    assert counts['active'] == 1
    assert counts['source_unknown'] == 1
    assert counts['critical'] == 0
