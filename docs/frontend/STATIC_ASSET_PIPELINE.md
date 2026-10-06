# KAORI Static Asset Pipeline

## Purpose

KAORI serves frontend runtime assets from its own Flask static directory. Runtime pages must not depend on CDN availability, public internet access, or mutable remote package URLs.

## Canonical Sources and Outputs

| Asset | Source of truth | Runtime output |
|---|---|---|
| Tailwind CSS | `frontend/styles.css` and scanned templates/scripts | `app/static/css/output.css` |
| Alpine.js | exact package version in `package.json` and `package-lock.json` | `app/static/vendor/alpine/alpine.min.js` |
| HTMX | exact package version in `package.json` and `package-lock.json` | `app/static/vendor/htmx/htmx.min.js` |
| Lucide | exact package version in `package.json` and `package-lock.json` | `app/static/vendor/lucide/lucide.min.js` |
| Chart.js | exact package version in `package.json` and `package-lock.json` | `app/static/vendor/chartjs/chart.umd.min.js` |

`node_modules` is a build workspace only and must not be committed or read by the KAORI production runtime.

## Commands

Initial synchronization when a dependency is added or its version changes:

```bash
npm run bootstrap-frontend
```

Normal development setup from an already synchronized lockfile:

```bash
npm ci --no-audit --no-fund
npm run prepare-frontend
```

UI development with automatic Tailwind rebuild:

```bash
npm run watch-css
```

One-time complete build and verification:

```bash
npm run prepare-frontend
```

Verification only:

```bash
npm run verify-frontend
./scripts/test_offline_frontend.sh
```

## Development Flow

1. Run `npm ci` after cloning, rebuilding the Dev Container, or changing `package-lock.json`.
2. Run `npm run prepare-frontend` to generate local vendor files and compiled CSS.
3. During template or styling work, run `npm run watch-css` in a dedicated terminal.
4. Before commit, stop the watcher and run `npm run prepare-frontend` again.
5. Run frontend functional and contract tests.
6. Commit source, lockfile, generated vendor files, compiled CSS, tests, and documentation together.

`watch-css` is a developer convenience only. It must not run in production, Celery workers, or Kubernetes application pods.

## Dependency Update Flow

Use exact versions only. Do not use `latest`, caret ranges, tilde ranges, or wildcard versions.

```bash
npm install --save-dev --save-exact <package>@<version>
npm run prepare-frontend
./scripts/test_offline_frontend.sh
```

Review and commit:

- `package.json`
- `package-lock.json`
- `app/static/vendor/**`
- `app/static/css/output.css`
- related tests
- this documentation when the process changes

## Runtime Contract

KAORI templates must reference local paths such as:

```jinja2
{{ url_for('static', filename='vendor/htmx/htmx.min.js') }}
{{ url_for('static', filename='vendor/lucide/lucide.min.js') }}
{{ url_for('static', filename='css/output.css') }}
```

The following runtime references are prohibited:

- `cdn.jsdelivr.net`
- `unpkg.com`
- `cdnjs.cloudflare.com`
- `cdn.tailwindcss.com`
- `fonts.googleapis.com`
- `fonts.gstatic.com`

## Icon Initialization

Lucide must be loaded before icon initialization. Layout or application JavaScript should call `lucide.createIcons()` after the DOM is ready and after HTMX swaps when newly inserted fragments contain `data-lucide` attributes.

Recommended behavior:

```javascript
document.addEventListener('DOMContentLoaded', () => {
  window.lucide?.createIcons();
});

document.body.addEventListener('htmx:afterSwap', () => {
  window.lucide?.createIcons();
});
```

A missing vendor file, invalid icon name, or missing post-swap initialization must be treated as a frontend defect, not hidden with a CDN fallback.

## Git Policy

Frontend dependency and asset pipeline changes use a dedicated commit after tests pass, for example:

```text
fix(frontend): complete offline static asset pipeline
```
