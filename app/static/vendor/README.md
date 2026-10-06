# KAORI Vendored Runtime Assets

Files in this directory are served by KAORI at runtime so the UI does not depend on a public CDN.

Managed packages:

- Alpine.js
- htmx
- Lucide
- Chart.js

Do not edit minified files manually. Update the exact versions in `package.json`, run
`npm install`, then run `npm run vendor-assets`. Commit the generated files,
`manifest.json`, package lock, tests, and template changes together.

Cytoscape remains independently managed by its existing integration.
