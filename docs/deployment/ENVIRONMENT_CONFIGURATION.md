# KAORI Environment Configuration

KAORI uses one canonical environment-variable contract across environments. Copy `.env.example` to `.env` for development and `.env.production.example` to `.env.production` on the production host. Real environment files and credentials must never be committed.

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

Telegram credentials for Intelligence notification channels are **not** environment variables. Notification Channels store provider credentials encrypted per channel. `ALERT_INTELLIGENCE_NOTIFICATION_*` and `NOTIFICATION_DELIVERY_*` only control the background dispatcher and provider delivery policy.

Scheduled report Telegram delivery remains a separate report-delivery capability and currently uses `REPORT_TELEGRAM_BOT_TOKEN` and `REPORT_TELEGRAM_CHAT_ID`.

## Production validation

Before deploying production configuration, run:

```bash
python scripts/verify_environment_contract.py
python scripts/validate_production_env.py
```

`verify_environment_contract.py` prevents application/deployment settings from drifting out of `.env.example` or `.env.production.example`. `validate_production_env.py` validates security-sensitive and operational production values such as URLs, credentials, queue names, worker limits, notification delivery controls, and TLS governance windows.
