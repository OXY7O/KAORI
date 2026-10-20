"""Website-brand alignment contract for the unauthenticated login panel (#2408)."""

from pathlib import Path

from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[2]
BRAND_PANEL = ROOT / 'app/templates/access/authentication/partials/_brand_panel.html'
BRAND_CSS = ROOT / 'app/static/css/auth-login.css'
WEBSITE_ART = ROOT / 'app/static/images/kaori-website-capabilities.webp'
LOGIN_FORM = ROOT / 'app/templates/access/authentication/partials/_login_form.html'

CLARITY_COPY = 'Unified visibility and governed infrastructure operations.'


def test_login_brand_uses_local_website_artwork_and_single_line_copy() -> None:
    panel = BRAND_PANEL.read_text(encoding='utf-8')
    css = BRAND_CSS.read_text(encoding='utf-8')
    artwork = WEBSITE_ART.read_bytes()

    assert CLARITY_COPY in panel
    assert 'Operate with ' in panel
    assert 'kaori-website-capabilities.webp' in panel
    assert 'kaori-login-operations-fabric.svg' not in panel
    assert '_feature_cards.html' not in panel  # Four pillars already appear in the artwork.
    assert 'Visibility, Control, Intelligence and Assurance.' in panel
    assert 'white-space: nowrap;' in css
    assert artwork[:4] == b'RIFF' and artwork[8:12] == b'WEBP'
    assert 'lg:flex' in panel and 'hidden' in panel
    assert 'form.hidden_tag()' in LOGIN_FORM.read_text(encoding='utf-8')


def test_login_website_brand_responsive_geometry(
    configured_page: Page,
    kaori_base_url: str,
    kaori_viewport: tuple[str, tuple[int, int]],
) -> None:
    page = configured_page
    _, (width, _) = kaori_viewport
    response = page.goto(f'{kaori_base_url}/auth/login', wait_until='networkidle')
    assert response is not None and response.ok

    brand = page.locator('.kaori-login-brand')
    assert page.locator('.kaori-login-form-panel').is_visible()

    if width < 1024:
        assert not brand.is_visible()
        return

    assert brand.is_visible()
    description = brand.locator('.kaori-login-brand__description')
    assert description.inner_text().strip() == CLARITY_COPY

    metrics = description.evaluate(
        """el => {
          const style = getComputedStyle(el);
          const box = el.getBoundingClientRect();
          return {
            whiteSpace: style.whiteSpace,
            width: box.width,
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
            height: box.height,
            lineHeight: parseFloat(style.lineHeight),
          };
        }"""
    )
    assert metrics['whiteSpace'] == 'nowrap'
    assert metrics['scrollWidth'] <= metrics['clientWidth'] + 1
    assert metrics['height'] <= metrics['lineHeight'] + 1

    artwork = brand.locator('[data-kaori-login-website-artwork] img')
    assert artwork.is_visible()
    assert artwork.evaluate('(image) => image.complete && image.naturalWidth > 0')
    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
