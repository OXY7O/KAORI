"""Bounded Visual QA fingerprint resilience under source-proven one-channel raster noise."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest
from PIL import Image
from playwright.sync_api import Page

from tests.ui.visual_audit import (
    _matches_single_quantization_edge,
    _matches_single_white_quantization_edge,
    assert_visual_baseline,
)


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


def test_single_non_white_quantization_edge_recreates_exact_reviewed_sha() -> None:
    # One raw channel differs by one 8-bit level precisely at the 35/36
    # decision boundary; other color channels are unchanged.
    assert _matches_single_quantization_edge(
        bytes((34, 35, 36)),
        bytes((24, 24, 48)),
        _digest(24, 24, 24),
    )
    assert _matches_single_quantization_edge(
        bytes((34, 35, 35)),
        bytes((24, 24, 24)),
        _digest(24, 24, 48),
    )


def test_quantization_guard_rejects_two_changed_channels() -> None:
    assert not _matches_single_quantization_edge(
        bytes((36, 36, 35)),
        bytes((48, 48, 24)),
        _digest(24, 24, 24),
    )


def test_quantization_guard_rejects_non_boundary_drift() -> None:
    assert not _matches_single_quantization_edge(
        bytes((33, 34, 34)),
        bytes((24, 24, 24)),
        _digest(48, 24, 24),
    )


def test_quantization_guard_rejects_invalid_normalized_thumbnail() -> None:
    assert not _matches_single_quantization_edge(
        bytes((34, 35, 36)),
        bytes((24, 24, 24)),
        _digest(24, 24, 48),
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


def _test_page() -> Page:
    buffer = BytesIO()
    Image.new('RGB', (390, 844), (255, 255, 255)).save(buffer, format='PNG')
    page = Mock()
    page.screenshot.return_value = buffer.getvalue()
    return cast(Page, page)


def _manifest(tmp_path: Path, *, height: int = 844) -> Path:
    manifest = tmp_path / 'baseline.json'
    manifest.write_text(
        json.dumps({'welcome-light-mobile': {'width': 390, 'height': height, 'visual_sha256': '0' * 64}}),
        encoding='utf-8',
    )
    return manifest


def test_geometry_mismatch_fails_before_rounding_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.ui.visual_audit as visual

    def unexpected_guard(*_args: object) -> bool:
        raise AssertionError('edge guard cannot bypass geometry')

    monkeypatch.setattr(visual, '_matches_white_raster_rounding_noise', unexpected_guard)
    with pytest.raises(AssertionError, match='dimensions changed'):
        assert_visual_baseline(
            _test_page(),
            surface='welcome',
            theme='light',
            viewport_name='mobile',
            manifest_path=_manifest(tmp_path, height=800),
            evidence_root=tmp_path / 'evidence',
        )


def test_one_channel_guard_emits_visible_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.ui.visual_audit as visual

    monkeypatch.setattr(visual, '_matches_white_raster_rounding_noise', lambda *_: True)
    with pytest.warns(UserWarning, match='one near-white quantization-edge'):
        assert_visual_baseline(
            _test_page(),
            surface='welcome',
            theme='light',
            viewport_name='mobile',
            manifest_path=_manifest(tmp_path),
            evidence_root=tmp_path / 'evidence',
        )


def test_material_drift_still_fails_with_screenshot_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.ui.visual_audit as visual

    monkeypatch.setattr(visual, '_matches_white_raster_rounding_noise', lambda *_: False)
    evidence = tmp_path / 'evidence'
    with pytest.raises(AssertionError, match='visual baseline changed'):
        assert_visual_baseline(
            _test_page(),
            surface='welcome',
            theme='light',
            viewport_name='mobile',
            manifest_path=_manifest(tmp_path),
            evidence_root=evidence,
        )
    assert (evidence / 'welcome-light-mobile-actual.png').is_file()


def test_proven_raster_artifact_requires_approved_sha_and_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tests.ui.visual_audit as visual

    page = _test_page()
    actual_png = page.screenshot.return_value
    expected_sha = '0' * 64
    exact_png_sha = hashlib.sha256(actual_png).hexdigest()
    monkeypatch.setattr(
        visual,
        '_PROVEN_RASTER_VARIANTS',
        {'welcome-light-mobile': (expected_sha, exact_png_sha)},
    )

    assert visual._matches_proven_raster_variant('welcome-light-mobile', actual_png, expected_sha)
    assert not visual._matches_proven_raster_variant('welcome-light-mobile', actual_png + b'x', expected_sha)
    assert not visual._matches_proven_raster_variant('welcome-light-mobile', actual_png, '1' * 64)
    assert not visual._matches_proven_raster_variant('welcome-dark-mobile', actual_png, expected_sha)

    with pytest.warns(UserWarning, match='exact reviewed one-time raster artifact variant'):
        assert_visual_baseline(
            page,
            surface='welcome',
            theme='light',
            viewport_name='mobile',
            manifest_path=_manifest(tmp_path),
            evidence_root=tmp_path / 'evidence',
        )


def test_proven_raster_artifact_cannot_bypass_geometry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.ui.visual_audit as visual

    page = _test_page()
    actual_png = page.screenshot.return_value
    monkeypatch.setattr(
        visual,
        '_PROVEN_RASTER_VARIANTS',
        {'welcome-light-mobile': ('0' * 64, hashlib.sha256(actual_png).hexdigest())},
    )
    with pytest.raises(AssertionError, match='dimensions changed'):
        assert_visual_baseline(
            page,
            surface='welcome',
            theme='light',
            viewport_name='mobile',
            manifest_path=_manifest(tmp_path, height=800),
            evidence_root=tmp_path / 'evidence',
        )
