"""Bounded Visual QA fingerprint resilience under source-proven one-channel raster noise."""

from __future__ import annotations

import hashlib

from tests.ui.visual_audit import _matches_single_white_quantization_edge


def _digest(*channels: int) -> str:
    return hashlib.sha256(bytes(channels)).hexdigest()


def test_single_near_white_252_channel_matches_reviewed_251_quantization() -> None:
    # Exact real-run mechanism: unquantized RGB 250/249/252 versus 250/249/251
    # crosses the 24-unit top-white quantum in one channel of one thumbnail pixel.
    assert _matches_single_white_quantization_edge(
        bytes((250, 249, 252)),
        bytes((240, 240, 255)),
        _digest(240, 240, 240),
    )


def test_single_near_white_251_channel_matches_reviewed_252_quantization() -> None:
    assert _matches_single_white_quantization_edge(
        bytes((250, 249, 251)),
        bytes((240, 240, 240)),
        _digest(240, 240, 255),
    )


def test_two_changed_channel_buckets_cannot_pass_as_one_rounding_edge() -> None:
    assert not _matches_single_white_quantization_edge(
        bytes((252, 252, 250)),
        bytes((255, 255, 240)),
        _digest(240, 240, 240),
    )


def test_unrelated_color_change_cannot_use_white_boundary_exception() -> None:
    assert not _matches_single_white_quantization_edge(
        bytes((200, 249, 252)),
        bytes((192, 240, 255)),
        _digest(216, 240, 240),
    )


def test_wrong_dimensions_or_truncated_thumbnail_never_match() -> None:
    assert not _matches_single_white_quantization_edge(
        bytes((252, 249)),
        bytes((255, 240, 240)),
        _digest(240, 240, 240),
    )


def test_no_boundary_pixel_cannot_reinterpret_an_arbitrary_digest() -> None:
    assert not _matches_single_white_quantization_edge(
        bytes((80, 120, 160)),
        bytes((72, 120, 168)),
        _digest(72, 120, 144),
    )


def test_existing_exact_sha_authority_is_unchanged_for_any_noisy_candidate() -> None:
    # The edge guard does not replace or mutate the original exact digest.
    normalized = bytes((240, 240, 255))
    strict = hashlib.sha256(normalized).hexdigest()
    expected = _digest(240, 240, 240)
    assert strict != expected
    assert _matches_single_white_quantization_edge(bytes((250, 249, 252)), normalized, expected)
