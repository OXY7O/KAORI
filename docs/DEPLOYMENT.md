# KAORI Production Deployment

The canonical development and production runbook is maintained in [`RUN.md`](../RUN.md).

Production principles:

- Build the Dockerfile `production` target in CI.
- Deploy an immutable registry image tagged with a version or commit SHA.
- Keep PostgreSQL, Redis, and S3/MinIO credentials outside the repository.
- Validate production environment variables before migration.
- Back up PostgreSQL before every schema migration.
- Run migration once, separately from web startup.
- Bootstrap the first administrator only during initial installation.
- Place Gunicorn behind a trusted HTTPS reverse proxy.
