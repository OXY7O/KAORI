# KAORI Production Container Deployment

The production image is immutable and uses Gunicorn. Source code is copied into
the image and is not bind-mounted from the deployment host.

## Build

```bash
docker build --target production -t kaori:<version> .
```

Use a release version or Git commit SHA instead of relying only on `latest`.

## Configure

Copy `.env.production.example` to `.env.production` on the deployment host and
provide real secrets through a protected environment file, CI/CD secret store,
or external secret manager.

Production should normally use externally managed PostgreSQL, Redis, and
S3-compatible object storage. The base `compose.yml` infrastructure remains
available for a controlled single-host deployment.

## Migrate

```bash
docker compose --env-file .env.production -f compose.yml -f compose.production.yml run --rm migrate
```

Migration is intentionally separate from web startup so multiple web or worker
containers never race to update the database schema.

## Start web

```bash
docker compose --env-file .env.production -f compose.yml -f compose.production.yml up -d web
```

## Verify

```bash
docker compose --env-file .env.production -f compose.yml -f compose.production.yml ps
docker compose --env-file .env.production -f compose.yml -f compose.production.yml logs -f web
```

Health endpoints:

- `/health/live` checks whether the Flask process is alive.
- `/health/ready` checks PostgreSQL and Redis readiness.

## Report storage

S3-compatible storage is recommended for production. The production Compose file
also mounts `/app/instance` as a persistent volume for rendering staging and for
single-host local storage fallback.

## Future Celery services

Celery workers and Celery Beat will use the same `production` image. They will be
added as separate Compose services with dedicated commands and queues; they must
not run migrations or bootstrap administrators during startup.
