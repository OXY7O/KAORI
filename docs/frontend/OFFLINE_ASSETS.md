# Offline Frontend Runtime Assets

KAORI serves browser runtime dependencies from `app/static/vendor`. Public CDN access is not required after the assets are generated and committed.

## Pinned packages

| Package | Version | KAORI runtime path |
|---|---:|---|
| Alpine.js | 3.15.12 | `app/static/vendor/alpine/alpine.min.js` |
| htmx | 2.0.10 | `app/static/vendor/htmx/htmx.min.js` |
| Lucide | 1.20.0 | `app/static/vendor/lucide/lucide.min.js` |
| Chart.js | 4.5.1 | `app/static/vendor/chartjs/chart.umd.min.js` |

Google Fonts was removed. KAORI now uses a local system font stack, so no font download is required.

## Initial generation

The one-time generation step requires package registry access unless the packages already exist in the npm cache:

```bash
npm install --prefer-offline --no-audit --no-fund
npm run vendor-assets
npm run build-css
npm run verify-vendor-assets
```

The generated JavaScript and license files must be committed. Production and offline development do not need npm or internet access to serve them.

## Validation

```bash
./scripts/test_offline_frontend.sh
pytest -q -m "not debug"
```

Manual browser validation:

1. Open Developer Tools and select Network.
2. Enable Offline and Disable cache.
3. Hard-reload the login page.
4. Test Database login, authenticated navigation, HTMX requests, dropdowns, icons, charts, pagination, modals, and toast behavior.
5. Confirm all runtime files come from `/static/` and no request targets a CDN or Google Fonts.

Google and GitHub authentication still require their external identity-provider endpoints. Database authentication and internal LDAP can operate without public internet when their own dependencies are reachable.

## Upgrade procedure

1. Change exactly one package version in `package.json`.
2. Run `npm install --prefer-offline --no-audit --no-fund`.
3. Run `npm run vendor-assets`.
4. Review `app/static/vendor/manifest.json`, file size, license, and checksum changes.
5. Run the frontend functional and contract gates.
6. Perform browser smoke testing.
7. Commit the version, lockfile, generated static assets, manifest, tests, and documentation in one frontend dependency commit.
