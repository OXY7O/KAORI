from playwright.sync_api import Page, expect


def test_login_surface_renders_across_canonical_viewports(configured_page: Page, kaori_base_url: str) -> None:
    page = configured_page
    response = page.goto(f'{kaori_base_url}/login', wait_until='networkidle')

    assert response is not None
    assert response.ok
    expect(page.locator('body')).to_be_visible()
