from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'app/jobs/query_planning.py'
SPEC = spec_from_file_location('kaori_query_planning_contract', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

QueryBudgetPolicy = MODULE.QueryBudgetPolicy
build_query_chunks = MODULE.build_query_chunks
recommended_step_seconds = MODULE.recommended_step_seconds


def test_annual_query_is_split_into_bounded_chunks() -> None:
    start = datetime(2025, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 1, tzinfo=UTC)
    chunks = build_query_chunks(
        start=start,
        end=end,
        requested_step_seconds=60,
        policy=QueryBudgetPolicy(chunk_days=30, minimum_step_seconds=3600),
    )
    assert len(chunks) == 13
    assert chunks[0].start == start
    assert chunks[-1].end == end
    assert all(chunk.step_seconds >= 3600 for chunk in chunks)
    assert all((chunk.end - chunk.start).days <= 30 for chunk in chunks)


def test_sample_budget_can_raise_step_above_requested_floor() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)
    step = recommended_step_seconds(
        start=start,
        end=end,
        requested_step_seconds=60,
        policy=QueryBudgetPolicy(minimum_step_seconds=300, maximum_samples_per_series=100),
    )
    assert step >= 26784


def test_query_range_guard_rejects_unbounded_history() -> None:
    with pytest.raises(ValueError, match='exceeds'):
        build_query_chunks(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 2, tzinfo=UTC),
            requested_step_seconds=3600,
            policy=QueryBudgetPolicy(maximum_range_days=366),
        )
