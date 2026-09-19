# KAORI Frontend Asset Deployment

## Production Requirement

The production image must contain browser-ready files under:

```text
/app/app/static/css/output.css
/app/app/static/vendor/
```

The production runtime must not require Node.js, npm, `node_modules`, a package registry, or public internet access.

## Multi-stage Build Contract

The frontend build stage performs:

```text
npm ci
→ npm run build-frontend
→ npm run verify-frontend
```

The final Python runtime stage copies only the generated CSS and vendor directory from the frontend build stage.

Do not copy `node_modules` into the production image.

## Deployment Validation

Build the production image:

```bash
docker build --target production -t kaori:local .
```

Inspect expected files:

```bash
docker run --rm --entrypoint sh kaori:local -c '
  test -s /app/app/static/css/output.css &&
  test -s /app/app/static/vendor/alpine/alpine.min.js &&
  test -s /app/app/static/vendor/htmx/htmx.min.js &&
  test -s /app/app/static/vendor/lucide/lucide.min.js &&
  test -s /app/app/static/vendor/chartjs/chart.umd.min.js &&
  test -s /app/app/static/vendor/manifest.json
'
```

Run KAORI and verify HTTP 200 responses for:

```text
/static/css/output.css
/static/vendor/alpine/alpine.min.js
/static/vendor/htmx/htmx.min.js
/static/vendor/lucide/lucide.min.js
/static/vendor/chartjs/chart.umd.min.js
```

## Offline Validation

1. Open KAORI in the browser.
2. Open Developer Tools and select Network.
3. Enable Disable cache.
4. Hard reload and confirm every CSS/JS request is served by the KAORI host.
5. Switch the browser to Offline mode.
6. Reload a previously opened page and test navigation, icons, dropdowns, HTMX updates, modals, toasts, and charts.
7. Confirm no request targets an external CDN or public font provider.

Google and GitHub authentication still require connectivity to their identity-provider endpoints. Local Database authentication and internal LDAP authentication can remain usable without public internet, subject to their own network availability.

## Rollback

Rollback the dedicated frontend commit:

```bash
git revert <frontend-commit-sha>
```

Then rebuild the image. Do not manually delete individual generated vendor files because that can leave templates, lockfile, manifest, and runtime assets inconsistent.

## Release Gate

A release is blocked when any of the following occurs:

- `package.json` and `package-lock.json` disagree.
- A required vendor asset is missing or empty.
- Vendor integrity verification fails.
- Compiled CSS is stale.
- A template references a CDN.
- The production image omits `app/static/vendor`.
- Lucide icons fail after initial load or an HTMX swap.
