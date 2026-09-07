from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
STATE_MARKERS = {
    'setup_required': 'Schema Missing',
    'database_unavailable': 'PostgreSQL Unavailable',
}


def _capture_evidence(page: Page, state: str, viewport_name: str) -> None:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(EVIDENCE_ROOT / f'{state}-{viewport_name}.png'),
        full_page=True,
        animations='disabled',
    )


def test_authentication_readiness_state_is_responsive_and_traceable(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_unready_base_url: tuple[str, str],
) -> None:
    page = configured_page
    viewport_name, _ = kaori_viewport
    state, base_url = kaori_unready_base_url
    trace_path = EVIDENCE_ROOT / f'{state}-{viewport_name}-trace.zip'
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)

    page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
    try:
        response = page.goto(f'{base_url}/auth/login', wait_until='networkidle')
        assert response is not None
        assert response.status == 503
        expect(page.get_by_role('heading', name='Database Setup Required')).to_be_visible()
        expect(page.get_by_text(STATE_MARKERS[state], exact=True)).to_be_visible()

        layout = page.evaluate(
            """() => ({
                scrollWidth: document.documentElement.scrollWidth,
                clientWidth: document.documentElement.clientWidth,
                bodyScrollWidth: document.body.scrollWidth,
            })"""
        )
        assert isinstance(layout, dict)
        assert layout['scrollWidth'] <= layout['clientWidth'] + 1
        assert layout['bodyScrollWidth'] <= layout['clientWidth'] + 1
    finally:
        _capture_evidence(page, state, viewport_name)
        page.context.tracing.stop(path=str(trace_path))
