from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]


def test_login_surface_renders_across_canonical_viewports(configured_page: Page, kaori_base_url: str) -> None:
    page = configured_page
    response = page.goto(f'{kaori_base_url}/login', wait_until='networkidle')

    assert response is not None
    assert response.ok
    expect(page.locator('body')).to_be_visible()



def test_numeric_pagination_survives_repeated_htmx_renders(page: Page) -> None:
    """A second HTMX render must not turn KAORI's numeric links into inert anchors."""
    page.set_content(
        """
        <section id="namespace-table">
          <span hx-select="#namespace-table" hx-push-url="true">
            <span data-kaori-numeric-pagination data-current-page="1"
                  data-total-pages="5" data-page-param="page">
              <span aria-current="page">1</span>
              <a href="/platform-operations/kubernetes/?tab=secret-reveal&amp;page=2"
                 hx-get="/platform-operations/kubernetes/secret-reveal/workspace?page=2"
                 hx-target="#namespace-table" hx-swap="innerHTML"
                 hx-select="#namespace-table" hx-indicator="#namespace-loader">2</a>
            </span>
          </span>
        </section>
        """
    )
    page.add_script_tag(path=str(ROOT / 'app/static/js/pagination.js'))
    page.evaluate("document.dispatchEvent(new Event('DOMContentLoaded'))")

    # KAORI's actual HTMX lifecycle invokes the renderer more than once per
    # request. Check each pass without reloading the browser.
    page.evaluate(
        """async () => {
            const target = document.getElementById('namespace-table');
            for (const name of ['htmx:afterSwap', 'htmx:afterSettle']) {
                document.dispatchEvent(new CustomEvent(name, { detail: { target } }));
                await new Promise(requestAnimationFrame);
            }
            await new Promise(requestAnimationFrame);
        }"""
    )
    links = page.locator('[data-kaori-numeric-pagination] a')
    assert links.count() == 4
    for page_number in range(2, 6):
        link = page.locator('[data-kaori-numeric-pagination] a', has_text=str(page_number))
        href = link.get_attribute('href')
        partial = link.get_attribute('hx-get')
        assert href is not None and parse_qs(urlsplit(href).query)['page'] == [str(page_number)]
        assert partial is not None and parse_qs(urlsplit(partial).query)['page'] == [str(page_number)]
        assert link.get_attribute('hx-target') == '#namespace-table'
        assert link.get_attribute('hx-select') == '#namespace-table'

    # A user click must still reach a navigable link, even after both
    # lifecycle events have rerendered the pagination collection.
    page.evaluate(
        """() => {
            window.paginationTestClick = null;
            document.addEventListener('click', (event) => {
                const link = event.target.closest('[data-kaori-numeric-pagination] a');
                if (link) {
                    event.preventDefault();
                    window.paginationTestClick = {
                        href: link.getAttribute('href'),
                        partial: link.getAttribute('hx-get')
                    };
                }
            }, true);
        }"""
    )
    page.locator('[data-kaori-numeric-pagination] a', has_text='3').click()
    clicked = page.evaluate('window.paginationTestClick')
    assert clicked is not None
    assert parse_qs(urlsplit(clicked['href']).query)['page'] == ['3']
    assert parse_qs(urlsplit(clicked['partial']).query)['page'] == ['3']

    # A replacement response brings a new pagination window. Check that its
    # new source link is used rather than the old detached server-side source.
    page.evaluate(
        """async () => {
            const container = document.querySelector('[data-kaori-numeric-pagination]');
            container.dataset.currentPage = '2';
            container.innerHTML = '<a href="/platform-operations/kubernetes/?page=3" ' +
                'hx-get="/platform-operations/kubernetes/secret-reveal/workspace?page=3" ' +
                'hx-target="#namespace-table" hx-select="#namespace-table">3</a>';
            const target = document.getElementById('namespace-table');
            for (const name of ['htmx:afterSwap', 'htmx:afterSettle']) {
                document.dispatchEvent(new CustomEvent(name, { detail: { target } }));
                await new Promise(requestAnimationFrame);
            }
            await new Promise(requestAnimationFrame);
        }"""
    )
    expect(page.locator('[data-kaori-numeric-pagination] [aria-current="page"]')).to_have_text('2')
    next_link = page.locator('[data-kaori-numeric-pagination] a', has_text='3')
    assert parse_qs(urlsplit(next_link.get_attribute('hx-get') or '').query)['page'] == ['3']



def test_verify_session_link_focuses_step_up_after_htmx_replacement(page: Page) -> None:
    """Verify Session must navigate and focus, even after HTMX swaps table rows."""
    html = """
    <!doctype html><html><body>
      <div data-secret-reveal-workspace>
        <section data-secret-reveal-panel="mine">
          <div style="height:500px"></div>
          <section id="reveal-session-step-up" tabindex="-1">
            <h2>Reveal Session Step-Up</h2>
            <label>Current KAORI Password
              <input type="password" name="password" data-reveal-step-up-password>
            </label>
          </section>
          <div style="height:850px"></div>
          <div id="my-requests-table">
            <a data-reveal-step-up-trigger
               href="/reveal?reveal_view=mine#reveal-session-step-up">Verify Session</a>
          </div>
        </section>
      </div>
    </body></html>
    """
    page.route(
        "http://kaori.test/**",
        lambda route: route.fulfill(status=200, content_type="text/html", body=html),
    )
    page.goto("http://kaori.test/reveal?reveal_view=mine&my_page=2")
    page.add_script_tag(path=str(ROOT / "app/static/js/secret_reveal_workspace.js"))
    page.evaluate(
        """() => {
            window.stepUpScrollCalls = 0;
            const target = document.getElementById('reveal-session-step-up');
            const original = target.scrollIntoView.bind(target);
            target.scrollIntoView = (options) => {
                window.stepUpScrollCalls += 1;
                original(options);
            };
        }"""
    )

    page.get_by_role("link", name="Verify Session").click()
    expect(page.locator("[data-reveal-step-up-password]")).to_be_focused()
    assert page.evaluate("window.stepUpScrollCalls") == 1
    assert urlsplit(page.url).fragment == "reveal-session-step-up"
    assert parse_qs(urlsplit(page.url).query)["my_page"] == ["2"]
    assert parse_qs(urlsplit(page.url).query)["reveal_view"] == ["mine"]

    # Poll/filter updates replace the table. Delegation keeps the action live.
    page.evaluate(
        """() => {
            document.querySelector('#my-requests-table').innerHTML =
              '<a data-reveal-step-up-trigger href="/reveal?reveal_view=mine#reveal-session-step-up">' +
              '<i data-lucide="fingerprint"></i><span>Verify Session</span></a>';
            document.activeElement.blur();
        }"""
    )
    page.get_by_role("link", name="Verify Session").click()
    expect(page.locator("[data-reveal-step-up-password]")).to_be_focused()
    assert page.evaluate("window.stepUpScrollCalls") == 2

    # Without a password input (external identity), focus the guidance panel.
    page.locator("[data-reveal-step-up-password]").evaluate("(element) => element.remove()")
    page.get_by_role("link", name="Verify Session").click()
    expect(page.locator("#reveal-session-step-up")).to_be_focused()
    assert page.evaluate("window.stepUpScrollCalls") == 3
