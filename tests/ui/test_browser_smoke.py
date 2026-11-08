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
        'http://kaori.test/**',
        lambda route: route.fulfill(status=200, content_type='text/html', body=html),
    )
    page.goto('http://kaori.test/reveal?reveal_view=mine&my_page=2')
    page.add_script_tag(path=str(ROOT / 'app/static/js/secret_reveal_workspace.js'))
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

    page.get_by_role('link', name='Verify Session').click()
    expect(page.locator('[data-reveal-step-up-password]')).to_be_focused()
    assert page.evaluate('window.stepUpScrollCalls') == 1
    assert urlsplit(page.url).fragment == 'reveal-session-step-up'
    assert parse_qs(urlsplit(page.url).query)['my_page'] == ['2']
    assert parse_qs(urlsplit(page.url).query)['reveal_view'] == ['mine']

    # Poll/filter updates replace the table. Delegation keeps the action live.
    page.evaluate(
        """() => {
            document.querySelector('#my-requests-table').innerHTML =
              '<a data-reveal-step-up-trigger href="/reveal?reveal_view=mine#reveal-session-step-up">' +
              '<i data-lucide="fingerprint"></i><span>Verify Session</span></a>';
            document.activeElement.blur();
        }"""
    )
    page.get_by_role('link', name='Verify Session').click()
    expect(page.locator('[data-reveal-step-up-password]')).to_be_focused()
    assert page.evaluate('window.stepUpScrollCalls') == 2

    # Without a password input (external identity), focus the guidance panel.
    page.locator('[data-reveal-step-up-password]').evaluate('(element) => element.remove()')
    page.get_by_role('link', name='Verify Session').click()
    expect(page.locator('#reveal-session-step-up')).to_be_focused()
    assert page.evaluate('window.stepUpScrollCalls') == 3


def test_verify_session_does_not_overscroll_kaori_main_viewport(page: Page) -> None:
    """The action must not shift an already visible Step-Up or overscroll the shell."""
    html = """
        <!doctype html><html><head><style>
          html, body { height: 100%; margin: 0; overflow: hidden; }
          [data-kaori-main-scroll] { height: 380px; overflow-y: auto; }
          .before { height: 54px; }
          #reveal-session-step-up { height: 185px; }
          .spacer { height: 900px; }
        </style></head><body>
          <main data-kaori-main-scroll>
            <div data-secret-reveal-workspace>
              <section data-secret-reveal-panel="mine">
                <div class="before"></div>
                <section id="reveal-session-step-up" tabindex="-1">
                  <label>Password <input data-reveal-step-up-password type="password"></label>
                </section>
                <div class="spacer"></div>
                <a data-reveal-step-up-trigger
                   href="/reveal?reveal_view=mine#reveal-session-step-up">
                   Verify Session
                </a>
              </section>
            </div>
          </main>
        </body></html>
        """
    page.route(
        'http://kaori.test/**',
        lambda route: route.fulfill(status=200, content_type='text/html', body=html),
    )
    page.goto('http://kaori.test/reveal?reveal_view=mine')
    page.add_script_tag(path=str(ROOT / 'app/static/js/secret_reveal_workspace.js'))
    page.evaluate(
        """() => {
            const main = document.querySelector('[data-kaori-main-scroll]');
            window.scrollMeasurements = [];
            const original = main.scrollTo.bind(main);
            main.scrollTo = (options) => {
                window.scrollMeasurements.push(options);
                original(options);
            };
        }"""
    )

    # The Step-Up is already on-screen, so repeated clicks must not move the
    # dashboard or expose a blank strip below its nested scrolling surface.
    page.evaluate("""() => document.querySelector('[data-reveal-step-up-trigger]').click()""")
    expect(page.locator('[data-reveal-step-up-password]')).to_be_focused()
    assert page.evaluate("document.querySelector('[data-kaori-main-scroll]').scrollTop") == 0
    assert page.evaluate('window.scrollMeasurements.length') == 0

    # Move only the main scroll container away from the Step-Up. The handler
    # must move that container back within its natural min/max scroll bounds.
    page.evaluate(
        """() => {
            const main = document.querySelector('[data-kaori-main-scroll]');
            main.scrollTop = 750;
            document.querySelector('[data-reveal-step-up-trigger]').click();
        }"""
    )
    expect(page.locator('[data-reveal-step-up-password]')).to_be_focused()
    result = page.evaluate(
        """() => {
            const main = document.querySelector('[data-kaori-main-scroll]');
            return {
                y: main.scrollTop,
                maxY: main.scrollHeight - main.clientHeight,
                bodyY: document.documentElement.scrollTop,
                calls: window.scrollMeasurements
            };
        }"""
    )
    assert len(result['calls']) == 1
    assert result['calls'][0]['behavior'] == 'auto'
    assert 0 <= result['y'] <= result['maxY']
    assert result['y'] < 750
    assert result['bodyY'] == 0
    assert urlsplit(page.url).fragment == 'reveal-session-step-up'


def test_my_requests_owns_temporary_reveal_and_clears_on_tab_change(page: Page) -> None:
    """One-time values are visible only in My Requests and cleared on leaving it."""
    page.set_content(
        """
        <main data-kaori-main-scroll style="height:500px;overflow-y:auto">
          <div data-secret-reveal-workspace>
            <section data-secret-reveal-panel="mine">
              <div id="reveal-session-step-up">Verified</div>
              <div id="reveal-value-output" hx-history="false"
                   role="region" aria-label="One-Time Secret Reveal Result"
                   tabindex="-1"></div>
              <section id="my-secret-reveal-requests">My Reveal Requests</section>
            </section>
          </div>
        </main>
        """
    )
    page.add_script_tag(path=str(ROOT / 'app/static/js/secret_reveal_value.js'))
    page.add_script_tag(path=str(ROOT / 'app/static/js/secret_reveal_workspace.js'))
    page.evaluate(
        """() => {
            const host = document.querySelector('#reveal-value-output');
            host.innerHTML = '<section data-protected-value-panel data-expires-in="60">' +
                '<span data-protected-value-countdown>60s</span>' +
                '<pre data-protected-value>synthetic-test-value</pre>' +
                '</section>';
            document.dispatchEvent(new CustomEvent('htmx:afterSwap', { detail: { target: host } }));
            document.dispatchEvent(new CustomEvent('htmx:load', { detail: { elt: host } }));
        }"""
    )
    expect(page.locator('#reveal-value-output')).to_be_focused()
    expect(page.locator('[data-protected-value]')).to_have_text('synthetic-test-value')
    assert page.locator('#reveal-value-output').get_attribute('hx-history') == 'false'
    page.evaluate(
        """() => window.dispatchEvent(new CustomEvent('secret-reveal:tab-changed', {
            detail: { tab: 'new' }
        }))"""
    )
    expect(page.locator('[data-protected-value]')).to_have_count(0)
    expect(page.locator('[data-protected-value-panel]')).to_contain_text(
        'The one-time Secret value was cleared when leaving My Requests.'
    )


def test_continue_to_approved_requests_scrolls_only_main_and_focuses_action(page: Page) -> None:
    """Do not native-anchor-scroll the whole KAORI shell to the tall registry."""
    html = """
        <!doctype html><html><head><style>
            html, body { margin:0; height:100%; overflow:hidden; }
            [data-kaori-main-scroll] { height:360px; overflow-y:auto; }
            .spacer { height:750px; }
        </style></head><body>
          <main data-kaori-main-scroll>
            <div data-secret-reveal-workspace>
              <section data-secret-reveal-panel="mine">
                <a data-reveal-approved-requests-trigger
                   href="#my-secret-reveal-requests">Continue to Approved Requests</a>
                <div class="spacer"></div>
                <section id="my-secret-reveal-requests" tabindex="-1">
                  <button type="submit" data-reveal-once-action>Reveal Once</button>
                </section>
              </section>
            </div>
          </main>
        </body></html>
    """
    page.route(
        'http://kaori.test/**',
        lambda route: route.fulfill(status=200, content_type='text/html', body=html),
    )
    page.goto('http://kaori.test/reveal?reveal_view=mine&my_page=2')
    page.add_script_tag(path=str(ROOT / 'app/static/js/secret_reveal_workspace.js'))
    page.evaluate(
        """() => {
            const main = document.querySelector('[data-kaori-main-scroll]');
            window.approvedScrollCalls = [];
            const original = main.scrollTo.bind(main);
            main.scrollTo = (opts) => {
                window.approvedScrollCalls.push(opts);
                original(opts);
            };
        }"""
    )
    page.get_by_role('link', name='Continue to Approved Requests').click()
    expect(page.locator('[data-reveal-once-action]')).to_be_focused()
    first = page.evaluate(
        """() => {
            const main = document.querySelector('[data-kaori-main-scroll]');
            return {
                scrollTop: main.scrollTop,
                maxScroll: main.scrollHeight - main.clientHeight,
                documentScroll: document.documentElement.scrollTop,
                calls: window.approvedScrollCalls
            };
        }"""
    )
    assert len(first['calls']) == 1
    assert first['calls'][0]['behavior'] == 'auto'
    assert 0 < first['scrollTop'] <= first['maxScroll']
    assert first['documentScroll'] == 0
    assert parse_qs(urlsplit(page.url).query)['my_page'] == ['2']
    assert urlsplit(page.url).fragment == 'my-secret-reveal-requests'

    # Clicking the CTA again while its target is visible must not scroll.
    # Use the DOM click to avoid Playwright scrolling the link itself into view.
    page.evaluate("""() => document.querySelector('[data-reveal-approved-requests-trigger]').click()""")
    expect(page.locator('[data-reveal-once-action]')).to_be_focused()
    assert page.evaluate('window.approvedScrollCalls.length') == 1

    # HTMX may replace My Requests and remove all approved rows. The CTA
    # must focus the registry header instead of jumping a full-screen card.
    page.evaluate(
        """() => {
            document.querySelector('[data-reveal-once-action]').remove();
            document.querySelector('[data-reveal-approved-requests-trigger]').click();
        }"""
    )
    expect(page.locator('#my-secret-reveal-requests')).to_be_focused()
    final = page.evaluate(
        """() => {
            const main = document.querySelector('[data-kaori-main-scroll]');
            return { y: main.scrollTop, maxY: main.scrollHeight - main.clientHeight,
                     bodyY: document.documentElement.scrollTop };
        }"""
    )
    assert 0 <= final['y'] <= final['maxY']
    assert final['bodyY'] == 0
