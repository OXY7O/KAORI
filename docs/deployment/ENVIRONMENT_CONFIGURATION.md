# KAORI Environment Configuration

KAORI uses one canonical variable inventory with explicit ownership by runtime. The templates are intentionally not identical: development is comprehensive for the Dev Container, the disposable RC-image example is minimal, and production separates application configuration, runtime secrets, deployment-adapter configuration, and generated immutable release identity. Real environment files and credentials must never be committed.

## Environment authorities

Use the template that owns the runtime you are configuring:

- `.env.example` is the comprehensive **development / Dev Container** contract. Copy it to `.env` before opening the Dev Container.
- `example/kaori/.env.example` is the intentionally minimal **disposable RC-image** example. It may omit optional settings and relies on safe application defaults baked into the image where appropriate; it is not a production template.
- `deploy/env/app.env.example` owns portable **production application configuration**.
- `deploy/env/secrets.env.example` owns **production runtime secrets**. Example values must remain placeholders; real credentials must not be committed.
- `deploy/env/deploy.env.example` owns **deployment-adapter configuration** used by the production deployment machinery.
- `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` are **generated immutable release identity**. They are supplied by the release process and intentionally do not belong in persistent production templates.
- Optional feature and provider configuration belongs to its documented application authority when enabled; minimal examples may omit it intentionally.

`.env.production.example` is deprecated and inactive. Do not copy it to create a production environment. Production configuration must use the split authorities under `deploy/env/` plus generated release identity.

## Why the templates have different sizes

The Dev Container contract is intentionally comprehensive because engineering needs supported settings to be discoverable and directly overridable during development.

The disposable RC-image example is intentionally minimal because it runs an already-admitted production image. It overrides only release identity, disposable local credentials/bootstrap values, localhost publication, and proxy trust; reviewed safe application defaults remain owned by application source and the image.

Production is intentionally split by responsibility so portable application policy, runtime secrets, deployment-adapter settings, and generated immutable release identity can change independently without recreating a monolithic environment file.

## Naming contract

Environment-specific prefixes are not used for application settings. The same canonical keys configure report and archive storage in development and production:

- `REPORT_*` controls report storage, staging, delivery, and report worker behavior.
- `ARCHIVE_*` controls reusable archive storage and lifecycle behavior.
- `KAORI_PUBLIC_BASE_URL` is the canonical externally reachable KAORI URL used by generated links and outbound notifications.

Legacy `DEV_REPORT_*`, `DEV_ARCHIVE_*`, `PROD_REPORT_*`, `PROD_ARCHIVE_*`, and `REPORT_PUBLIC_BASE_URL` keys are not supported.

## Operational groups

The environment templates document these runtime groups:

- application identity, release metadata, public URL, and integration credential encryption;
- database, Redis, rate limiting, authentication, and reverse-proxy trust;
- Kubernetes Secret reveal and TLS certificate governance windows;
- report/archive storage and data-retention policy;
- integration runtime monitoring and validation workers;
- analytics, forecasting, report, maintenance, and resolver workers;
- Object Storage inventory usage-statistics policy;
- Alert Intelligence notification-dispatch scheduling and delivery retry/timeout controls.

Provider credentials for platform Notification Channels are **not** environment variables. Notification Channels store provider credentials encrypted per channel. `ALERT_INTELLIGENCE_NOTIFICATION_*` and `NOTIFICATION_DELIVERY_*` only control the background dispatcher and provider delivery policy.

Scheduled Reports use reusable Notification Channels configured under Integrations. Provider credentials stay encrypted per channel in the database; report schedules store only selected channel identities.

## Production validation

Before deploying production configuration, populate the split production authorities under `deploy/env/`, supply release identity through the release process, and run:

```bash
python scripts/verify_environment_contract.py
python scripts/validate_production_env.py
```

`verify_environment_contract.py` protects the one-owner split production contract, development contract, sensitive-key placement, deployment-adapter ownership, generated release identity, and the requirement that `.env.production.example` remain deprecated and inactive. `validate_production_env.py` validates security-sensitive and operational production values such as URLs, credentials, queue names, worker limits, notification delivery controls, and TLS governance windows.
