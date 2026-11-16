"""Regression coverage for fail-closed ZAP JSON numeric parsing.

These tests use synthetic values only; never store raw scan evidence.
"""

import pytest

from scripts.ci_zap_safe_summary import (
    UnverifiedZapReport,
    _bounded_int,
    _finite_float,
    _reject_constant,
)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_constants_are_rejected(value):
    with pytest.raises(UnverifiedZapReport, match="Non-finite JSON number"):
        _reject_constant(value)


@pytest.mark.parametrize("value", ["1e9999", "-1e9999", "9" * 129])
def test_non_finite_or_oversized_floats_are_rejected(value):
    with pytest.raises(UnverifiedZapReport):
        _finite_float(value)


def test_oversized_integer_is_rejected_before_conversion():
    with pytest.raises(UnverifiedZapReport, match="Excessive JSON integer"):
        _bounded_int("9" * 21)


def test_bounded_numeric_values_are_accepted():
    assert _bounded_int("123") == 123
    assert _finite_float("1.25") == 1.25
