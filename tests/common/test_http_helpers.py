from __future__ import annotations

import pytest

from app.common.http import header_is_true, htmx_target, is_htmx_request

pytestmark = pytest.mark.functional


def test_header_is_true_is_case_and_whitespace_tolerant() -> None:
    assert header_is_true({'HX-Request': ' TRUE '}, 'HX-Request') is True
    assert header_is_true({'HX-Request': 'false'}, 'HX-Request') is False
    assert header_is_true({}, 'HX-Request') is False


def test_htmx_helpers_accept_explicit_headers_without_request_context() -> None:
    headers = {'HX-Request': 'true', 'HX-Target': ' runtime-panel '}

    assert is_htmx_request(headers) is True
    assert htmx_target(headers) == 'runtime-panel'
