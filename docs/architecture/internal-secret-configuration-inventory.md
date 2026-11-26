# Internal Secret Store configuration inventory (#5206)

Status: **names-only design proposal**. Baseline `kaori/staging@39d865eacd26b156400ae48159d6b48b451bd373`.
This inventory records assignments declared in tracked example files, not
live ENV, effective values, deployed topology or a migration authorization.
See [bootstrap model](internal-secret-configuration-bootstrap.md) and
[server deployment contract](../../deploy/server/README.md).

## Current authority and exposure

| Source | Declared names | Current owner / delivery boundary | Proposed treatment |
| --- | ---: | --- | --- |
| app.env.example | 221 | Application operator; shared application/worker and one-shot services | Retain declarative configuration, validate typed settings |
| secrets.env.example | 18 | Runtime secret custodian; shared application/worker and Redis/one-shot services | Classify individually below; do not migrate as a bundle |
| deploy.env.example | 11 | Target deployment operator; Compose/deployment selector | Keep independent of OpenBao |
| postgres-admin.env.example | 1 | DBA; PostgreSQL and db-provision | Independent recovery and provisioning |
| postgres-migrate.env.example | 1 | DBA/migration owner; migrate and db-provision | Separate privileged migration identity |
| secret-store.env.example | 1 | Secret Store operator; candidate OpenBao service only | Independent bootstrap root |
| .env.example | 238 | Local development example, not server authority | No automatic production import |

The six split examples declare 253 assignments
(253 unique names). The root example overlaps them and is not a
second production source. Counts exclude comments, generated release.env
and dynamically supplied deployment options. Protected workflow references
are separately recorded below. No live inventory was performed.

The current server Compose adapter sends the shared application and secret
files to web, worker, registry-security-worker, maintenance-worker,
runtime-worker, validation-worker, analytics-worker, reports-worker,
forecasting-worker, resolver-execution-worker, resolver-maintenance-worker
and beat, plus one-shot validation, migration, verification, provisioning
and administrator bootstrap where configured. Redis also receives the
shared secret file. This is an exposure observation, not evidence that
every recipient consumes every variable. Future per-component delivery
must reduce exposure without breaking startup, recovery or existing
release contracts. Validate actual code-level consumption before cutover.

## Runtime secret ownership and migration disposition

| Name(s) | Intended consumer / owner (review candidate) | Proposed disposition and failure boundary |
| --- | --- | --- |
| SECRET_KEY | Flask application/session signing | Independent recoverable key; migration/rotation needs session impact review |
| INTEGRATION_CREDENTIAL_KEY, INTEGRATION_CREDENTIAL_PREVIOUS_KEYS | Integration encryption/decryption | Retain existing key history until decryption and paired backup/restore prove compatibility; never rotate implicitly |
| DATABASE_URL | Application runtime, workers, DB verification | Independent runtime DB authentication during initial bootstrap; later bounded consumer only after recovery proof |
| REDIS_PASSWORD | Redis service, runtime custodian | Independent service bootstrap root; do not create circular dependency |
| REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, RATELIMIT_STORAGE_URI | Cache, task transport/results, rate-limit consumers | Treat as potentially credential-bearing URLs; coordinated rotation/connection validation |
| REPORT_S3_ACCESS_KEY_ID, REPORT_S3_SECRET_ACCESS_KEY | Report storage consumer | Future distinct report scope, credential pair atomic |
| ARCHIVE_S3_ACCESS_KEY_ID, ARCHIVE_S3_SECRET_ACCESS_KEY | Archive storage consumer | Future distinct archive scope, credential pair atomic |
| ADMIN_PASSWORD | One-shot administrator bootstrap | Privileged custody, not routine app/worker access; no automatic import |
| KAORI_LDAP_BIND_PASSWORD | Directory authentication | Future directory-specific scope; verify LDAPS and fallback/recovery |
| KAORI_GOOGLE_CLIENT_SECRET, KAORI_GITHUB_CLIENT_SECRET | SSO provider-specific authentication | Separate provider scope, rotation and login regression |
| RESOLVER_TOKEN_SIGNING_KEY | Resolver execution/signing | Separate signing authority; verify active token/rotation lifecycle |
| POSTGRES_PASSWORD | DBA / PostgreSQL / db-provision | Separate independent administrative identity |
| KAORI_DB_MIGRATION_URL | DBA / migrate / db-provision | Independent migrator credentials; not runtime identity |
| BAO_PG_CONNECTION_URL | OpenBao service | Independent restricted storage authentication; cannot reside solely inside OpenBao |

No actual value, hash of a secret, hostname, password, token or credential
material is included. The intended consumers above are review candidates,
not proof of effective access or complete code-level dependency mapping.

## Deployment and trust bootstrap

All eleven deploy.env example names remain target-owned:
`KAORI_APP_ENV_FILE`, `KAORI_SECRETS_ENV_FILE`, `KAORI_POSTGRES_ADMIN_ENV_FILE`, `KAORI_POSTGRES_MIGRATION_ENV_FILE`, `KAORI_ACTIVE_RELEASE_ENV_FILE`, `POSTGRES_DB`, `POSTGRES_USER`, `KAORI_BUNDLED_FRESH_BOOTSTRAP`, `KAORI_BUNDLED_SCHEMA_CUTOVER`, `KAORI_POSTGRES_IMAGE`, `KAORI_REDIS_IMAGE`.

The provider-selection and CA settings in app.env stay independently
available before OpenBao starts. Runtime target identity, release digest,
Compose project, trust, backup, recovery and state roots continue to follow
#5093 and the current server adapter. Do not infer isolation from GitHub
Environment name.

The four workflow sources deploy-staging-host.yml, release-image.yml,
environment-credential-preflight.yml and publish-staging-image.yml
reference these protected names (not their values):

- GitHub Secrets: KAORI_DOCKER_REGISTRY_PASSWORD,
  KAORI_DOCKER_REGISTRY_USERNAME, KAORI_HOST_KNOWN_HOSTS,
  KAORI_HOST_SSH_PASSPHRASE, KAORI_HOST_SSH_PRIVATE_KEY.
- GitHub Variables: KAORI_DOCKER_REGISTRY_HOST, KAORI_DOCKER_REGISTRY_IMAGE,
  KAORI_HOST, KAORI_HOST_DEPLOY_ROOT, KAORI_HOST_PORT, KAORI_HOST_USER.

Keep deployment authentication and host trust independent of the service
being deployed. This is a static source inventory, not a claim about
actual GitHub Environment configuration.

## Proposed initial automation scope (review required)

For #5172 only, the candidate mount is `kaori-automation` (KV v2),
candidate AppRole mount `kaori-automation-approle`, root namespace, and
credential path derived from the canonical SecretIdentity UUID:
`ssh/<uuid>`. See #5206 comment 7163465887. No naming acceptance is
implied by this document. Existing SecretProviderRepresentation and
SecretVersionObservation bind exact instance, namespace, mount, path digest
and version; issuer revision and #724 policy remain separate authorities.

Separate metadata observation, write-only onboarding/rotation and
worker-only exact-path read. A provider path ACL does not constrain a
specific KV version; current KAORI grant/issuer/version must independently
admit each use. No broad worker material permission, arbitrary paths,
root credentials, ENV migration or policy writer in this design increment.
Audit delivery and target approval must be verified before a separate
bounded apply implementation.

## Failure and recovery review matrix

| Failure | Required disposition before cutover |
| --- | --- |
| Sealed/unavailable provider | Deny new provider-dependent operations; retain independent bootstrap/recovery |
| Wrong provider/target/TLS/issuer | Reject; no alternate provider or silent fallback |
| Missing/revoked/expired scope or version | Deny; refresh committed evidence under approved workflow |
| Partial secret rotation | Stop affected consumer; independently approved paired rollback, no silent dual-write |
| Lost encryption key history | Block migration; prove restoration/decryption before cutover |
| Database/secret-store recovery mismatch | Restore a reviewed consistent recovery point; validate references and versions |
| Audit failure | Block sensitive operations; retain sanitized failure evidence |

## Exact app.env names (all 221 assignments)

Grouped by existing variable prefix for review, not new authorization
taxonomy. All remain declarative in this phase.

### Other application settings

`APP_ENV`, `KAORI_PUBLIC_BASE_URL`, `TRUSTED_HOSTS`, `RATELIMIT_ENABLED`, `KAORI_LDAP_CA_BUNDLE`, `WAIT_FOR_DB`, `DB_WAIT_ATTEMPTS`, `DB_WAIT_INTERVAL_SECONDS`, `DATA_LIFECYCLE_SCHEDULER_ENABLED`, `ACTIVITY_ARCHIVE_RETENTION_DAYS`, `RUNTIME_OBSERVATION_ARCHIVE_RETENTION_DAYS`, `OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE`, `CUSTOM_RUNBOOK_AUTHORING_ENABLED`.

### PROXY_FIX

`PROXY_FIX_ENABLED`, `PROXY_FIX_X_FOR`, `PROXY_FIX_X_PROTO`, `PROXY_FIX_X_HOST`, `PROXY_FIX_X_PORT`, `PROXY_FIX_X_PREFIX`.

### CELERY

`CELERY_RESULT_EXPIRES_SECONDS`, `CELERY_VISIBILITY_TIMEOUT_SECONDS`, `CELERY_LOG_LEVEL`, `CELERY_BEAT_LOG_LEVEL`, `CELERY_TIMEZONE`.

### INVENTORY

`INVENTORY_WORKER_CONCURRENCY`, `INVENTORY_WORKER_PREFETCH_MULTIPLIER`, `INVENTORY_MAX_TASKS_PER_CHILD`.

### REGISTRY_SECURITY

`REGISTRY_SECURITY_CELERY_QUEUE`, `REGISTRY_SECURITY_WORKER_CONCURRENCY`, `REGISTRY_SECURITY_WORKER_PREFETCH_MULTIPLIER`, `REGISTRY_SECURITY_MAX_TASKS_PER_CHILD`, `REGISTRY_SECURITY_WORKER_CPU_LIMIT`, `REGISTRY_SECURITY_WORKER_MEMORY_LIMIT`.

### RETENTION

`RETENTION_CELERY_QUEUE`, `RETENTION_RETRY_DELAY_SECONDS`.

### INTEGRATION_VAULT

`INTEGRATION_VAULT_ALLOWED_ORIGINS`, `INTEGRATION_VAULT_CA_BUNDLE`.

### INTEGRATION_OPENBAO

`INTEGRATION_OPENBAO_ALLOWED_ORIGINS`, `INTEGRATION_OPENBAO_CA_BUNDLE`.

### KAORI_INTERNAL_SECRET_STORE

`KAORI_INTERNAL_SECRET_STORE_PROVIDER`, `KAORI_INTERNAL_SECRET_STORE_ENDPOINT`.

### INTEGRATION_VALIDATION

`INTEGRATION_VALIDATION_CELERY_QUEUE`, `INTEGRATION_VALIDATION_LOCK_TTL_SECONDS`, `INTEGRATION_VALIDATION_WORKER_CONCURRENCY`, `INTEGRATION_VALIDATION_MAX_TASKS_PER_CHILD`, `INTEGRATION_VALIDATION_WORKER_CPU_LIMIT`, `INTEGRATION_VALIDATION_WORKER_MEMORY_LIMIT`.

### CLUSTER_SYNC

`CLUSTER_SYNC_LOCK_TTL_SECONDS`, `CLUSTER_SYNC_COMPLETED_TTL_SECONDS`.

### AUTH

`AUTH_LOGIN_RATE_LIMIT`, `AUTH_LOGIN_RATE_LIMIT_MESSAGE`, `AUTH_SSO_RATE_LIMIT`, `AUTH_SSO_RATE_LIMIT_MESSAGE`, `AUTH_SSO_FLOW_TTL_SECONDS`, `AUTH_REMEMBER_ME_DAYS`, `AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME`, `AUTH_LDAP_ALLOW_PLAINTEXT`.

### KUBERNETES_SECRET_REVEAL

`KUBERNETES_SECRET_REVEAL_ENABLED`, `KUBERNETES_SECRET_REVEAL_RATE_LIMIT`, `KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS`, `KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS`, `KUBERNETES_SECRET_REVEAL_MAX_BYTES`, `KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES`, `KUBERNETES_SECRET_REVEAL_PENDING_TTL_HOURS`.

### TLS_CERTIFICATE

`TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS`, `TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS`.

### REPORT

`REPORT_SCHEDULE_TIMEZONE`, `REPORT_PDF_CLASSIFICATION`, `REPORT_STORAGE_BACKEND`, `REPORT_LOCAL_STORAGE_DIR`, `REPORT_RENDER_STAGING_DIR`, `REPORT_DOWNLOAD_CACHE_DIR`, `REPORT_S3_BUCKET`, `REPORT_S3_REGION`, `REPORT_S3_ENDPOINT_URL`, `REPORT_S3_PREFIX`, `REPORT_S3_FORCE_PATH_STYLE`, `REPORT_S3_CONNECT_TIMEOUT_SECONDS`, `REPORT_S3_READ_TIMEOUT_SECONDS`, `REPORT_S3_MAX_ATTEMPTS`, `REPORT_STORAGE_STATUS_CACHE_SECONDS`, `REPORT_STORAGE_HEALTH_MONITOR_ENABLED`, `REPORT_STORAGE_HEALTH_INTERVAL_MINUTES`, `REPORT_STORAGE_HEALTH_STALE_SECONDS`, `REPORT_STORAGE_HEALTH_STATE_TTL_SECONDS`, `REPORT_STORAGE_HEALTH_CELERY_QUEUE`, `REPORT_RETENTION_DAYS`, `REPORT_ARCHIVE_RETENTION_DAYS`, `REPORT_ORPHAN_DETECTION_ENABLED`.

### ARCHIVE

`ARCHIVE_DOWNLOAD_CACHE_DIR`, `ARCHIVE_STAGING_DIR`, `ARCHIVE_OBJECT_PREFIX`, `ARCHIVE_PURGE_BATCH_SIZE`, `ARCHIVE_SCHEDULED_DOMAINS`.

### ACTIVITY_RETENTION

`ACTIVITY_RETENTION_ENABLED`, `ACTIVITY_RETENTION_DAYS`, `ACTIVITY_RETENTION_BATCH_SIZE`, `ACTIVITY_RETENTION_PROTECT_UNREVIEWED`, `ACTIVITY_RETENTION_PROTECTED_MAX_DAYS`, `ACTIVITY_RETENTION_SCHEDULE_ENABLED`, `ACTIVITY_RETENTION_SCHEDULE_HOUR`, `ACTIVITY_RETENTION_SCHEDULE_MINUTE`.

### JOB_EXECUTION_RETENTION

`JOB_EXECUTION_RETENTION_ENABLED`, `JOB_EXECUTION_RETENTION_DAYS`, `JOB_EXECUTION_RETENTION_BATCH_SIZE`, `JOB_EXECUTION_RETENTION_SCHEDULE_HOUR`, `JOB_EXECUTION_RETENTION_SCHEDULE_MINUTE`.

### JOB_EXECUTION

`JOB_EXECUTION_ARCHIVE_RETENTION_DAYS`, `JOB_EXECUTION_RUNTIME_RETENTION_DAYS`, `JOB_EXECUTION_VALIDATION_RETENTION_DAYS`, `JOB_EXECUTION_ANALYTICS_RETENTION_DAYS`, `JOB_EXECUTION_FORECASTING_RETENTION_DAYS`, `JOB_EXECUTION_FAILED_RETENTION_DAYS`.

### RUNTIME_OBSERVATION_RETENTION

`RUNTIME_OBSERVATION_RETENTION_ENABLED`, `RUNTIME_OBSERVATION_RETENTION_DAYS`, `RUNTIME_OBSERVATION_RETENTION_BATCH_SIZE`, `RUNTIME_OBSERVATION_RETENTION_SCHEDULE_HOUR`, `RUNTIME_OBSERVATION_RETENTION_SCHEDULE_MINUTE`.

### ANALYTICS_SNAPSHOT_RETENTION

`ANALYTICS_SNAPSHOT_RETENTION_ENABLED`, `ANALYTICS_SNAPSHOT_RETENTION_DAYS`, `ANALYTICS_SNAPSHOT_RETENTION_BATCH_SIZE`, `ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_HOUR`, `ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_MINUTE`.

### ANALYTICS

`ANALYTICS_SNAPSHOT_ARCHIVE_RETENTION_DAYS`, `ANALYTICS_CELERY_QUEUE`, `ANALYTICS_TASK_SOFT_TIME_LIMIT_SECONDS`, `ANALYTICS_TASK_HARD_TIME_LIMIT_SECONDS`, `ANALYTICS_TASK_MAX_SOFT_TIME_LIMIT_SECONDS`, `ANALYTICS_DATASET_TIMEOUT_SECONDS`, `ANALYTICS_SOURCE_LOCK_TIMEOUT_SECONDS`, `ANALYTICS_WORKER_CONCURRENCY`, `ANALYTICS_MAX_TASKS_PER_CHILD`, `ANALYTICS_WORKER_CPU_LIMIT`, `ANALYTICS_WORKER_MEMORY_LIMIT`.

### GENERATED_REPORT

`GENERATED_REPORT_RETENTION_ENABLED`, `GENERATED_REPORT_RETENTION_DAYS`, `GENERATED_REPORT_ARCHIVE_RETENTION_DAYS`, `GENERATED_REPORT_RETENTION_BATCH_SIZE`, `GENERATED_REPORT_FAILED_RETENTION_DAYS`, `GENERATED_REPORT_ARCHIVED_RETENTION_DAYS`, `GENERATED_REPORT_RETENTION_SCHEDULE_HOUR`, `GENERATED_REPORT_RETENTION_SCHEDULE_MINUTE`.

### GUNICORN

`GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_KEEPALIVE`, `GUNICORN_LOG_LEVEL`.

### ADMIN

`ADMIN_USERNAME`, `ADMIN_EMAIL`.

### SOURCE_CONTROL

`SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED`, `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED`.

### INTEGRATION_RUNTIME

`INTEGRATION_RUNTIME_MONITORING_ENABLED`, `INTEGRATION_RUNTIME_MONITORING_INTERVAL_MINUTES`, `INTEGRATION_RUNTIME_CELERY_QUEUE`, `INTEGRATION_RUNTIME_WORKER_CONCURRENCY`, `INTEGRATION_RUNTIME_MAX_TASKS_PER_CHILD`, `INTEGRATION_RUNTIME_WORKER_CPU_LIMIT`, `INTEGRATION_RUNTIME_WORKER_MEMORY_LIMIT`.

### FORECASTING

`FORECASTING_CELERY_QUEUE`, `FORECASTING_TASK_SOFT_TIME_LIMIT_SECONDS`, `FORECASTING_TASK_HARD_TIME_LIMIT_SECONDS`, `FORECASTING_TASK_MAX_SOFT_TIME_LIMIT_SECONDS`, `FORECASTING_DATASET_TIMEOUT_SECONDS`, `FORECASTING_WORKER_CONCURRENCY`, `FORECASTING_MAX_TASKS_PER_CHILD`, `FORECASTING_WORKER_CPU_LIMIT`, `FORECASTING_WORKER_MEMORY_LIMIT`.

### METRICS

`METRICS_SOURCE_ANALYTICS_QUERY_TIMEOUT_SECONDS`, `METRICS_SOURCE_ANALYTICS_RANGE_QUERY_TIMEOUT_SECONDS`, `METRICS_SOURCE_ANALYTICS_QUERY_RETRIES`, `METRICS_SOURCE_ANALYTICS_RETRY_BACKOFF_SECONDS`, `METRICS_RECENT_WINDOW_HOURS`.

### JOB_MAINTENANCE

`JOB_MAINTENANCE_CELERY_QUEUE`, `JOB_MAINTENANCE_WORKER_CONCURRENCY`, `JOB_MAINTENANCE_MAX_TASKS_PER_CHILD`, `JOB_MAINTENANCE_WORKER_CPU_LIMIT`, `JOB_MAINTENANCE_WORKER_MEMORY_LIMIT`.

### JOB

`JOB_POLICY_SCHEDULER_ENABLED`, `JOB_MAX_ACTIVE_PER_USER`, `JOB_MAX_HEAVY_PER_USER`, `JOB_MAX_ACTIVE_PER_RESOURCE`, `JOB_QUEUED_STALE_SECONDS`, `JOB_RUNNING_STALE_SECONDS`, `JOB_RECOVERY_ENABLED`, `JOB_RECOVERY_INTERVAL_MINUTES`.

### ALERT_SIGNAL

`ALERT_SIGNAL_EVALUATION_ENABLED`, `ALERT_SIGNAL_EVALUATION_INTERVAL_MINUTES`, `ALERT_SIGNAL_FRESHNESS_MINUTES`.

### ALERT_INTELLIGENCE

`ALERT_INTELLIGENCE_NOTIFICATION_ENABLED`, `ALERT_INTELLIGENCE_NOTIFICATION_INTERVAL_MINUTES`.

### NOTIFICATION

`NOTIFICATION_DELIVERY_TIMEOUT_SECONDS`, `NOTIFICATION_DELIVERY_MAX_ATTEMPTS`, `NOTIFICATION_NTFY_ALLOWED_ORIGINS`, `NOTIFICATION_NTFY_CA_BUNDLE`, `NOTIFICATION_DELIVERY_RECOVERY_ENABLED`, `NOTIFICATION_DELIVERY_RECOVERY_INTERVAL_MINUTES`, `NOTIFICATION_DELIVERY_RETRY_DELAY_SECONDS`.

### AUTOMATION

`AUTOMATION_EXECUTION_ENABLED`, `AUTOMATION_CANDIDATE_MATERIALIZATION_ENABLED`, `AUTOMATION_CANDIDATE_MATERIALIZATION_INTERVAL_MINUTES`, `AUTOMATION_LIFECYCLE_RECONCILIATION_ENABLED`.

### RESOLVER

`RESOLVER_ENABLED_ACTIONS`, `RESOLVER_KUBERNETES_ALLOWED_NAMESPACES`, `RESOLVER_EXECUTION_CELERY_QUEUE`, `RESOLVER_MAINTENANCE_CELERY_QUEUE`, `RESOLVER_MAINTENANCE_ENABLED`, `RESOLVER_MAINTENANCE_INTERVAL_MINUTES`, `RESOLVER_EXECUTION_WORKER_CONCURRENCY`, `RESOLVER_EXECUTION_MAX_TASKS_PER_CHILD`, `RESOLVER_EXECUTION_WORKER_CPU_LIMIT`, `RESOLVER_EXECUTION_WORKER_MEMORY_LIMIT`, `RESOLVER_MAINTENANCE_WORKER_CONCURRENCY`, `RESOLVER_MAINTENANCE_MAX_TASKS_PER_CHILD`, `RESOLVER_MAINTENANCE_WORKER_CPU_LIMIT`, `RESOLVER_MAINTENANCE_WORKER_MEMORY_LIMIT`.

### REPORTS

`REPORTS_CELERY_QUEUE`, `REPORTS_WORKER_CONCURRENCY`, `REPORTS_MAX_TASKS_PER_CHILD`, `REPORTS_WORKER_CPU_LIMIT`, `REPORTS_WORKER_MEMORY_LIMIT`.

## Root example differences

The following 16 names appear only in the root development
example relative to the six split examples; they are not automatically
admitted to server runtime:
`APP_VERSION`, `APP_BUILD_SHA`, `APP_BUILD_DATE`, `INTEGRATION_HARBOR_ALLOWED_ORIGINS`, `INTEGRATION_HARBOR_CA_BUNDLE`, `POSTGRES_PORT`, `REDIS_PORT`, `WAIT_FOR_SCHEMA`, `ARCHIVE_STORAGE_BACKEND`, `ARCHIVE_LOCAL_STORAGE_DIR`, `ARCHIVE_S3_BUCKET`, `ARCHIVE_S3_REGION`, `ARCHIVE_S3_ENDPOINT_URL`, `ARCHIVE_S3_PREFIX`, `ARCHIVE_S3_FORCE_PATH_STYLE`, `KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED`.

The following 31 names appear in the split examples but
not the root example; absence from local development does not establish
unused or obsolete status:
`TRUSTED_HOSTS`, `INTEGRATION_VALIDATION_WORKER_CPU_LIMIT`, `INTEGRATION_VALIDATION_WORKER_MEMORY_LIMIT`, `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_KEEPALIVE`, `GUNICORN_LOG_LEVEL`, `INTEGRATION_RUNTIME_WORKER_CPU_LIMIT`, `INTEGRATION_RUNTIME_WORKER_MEMORY_LIMIT`, `JOB_MAINTENANCE_WORKER_CPU_LIMIT`, `JOB_MAINTENANCE_WORKER_MEMORY_LIMIT`, `RESOLVER_EXECUTION_WORKER_CPU_LIMIT`, `RESOLVER_EXECUTION_WORKER_MEMORY_LIMIT`, `RESOLVER_MAINTENANCE_WORKER_CPU_LIMIT`, `RESOLVER_MAINTENANCE_WORKER_MEMORY_LIMIT`, `REDIS_PASSWORD`, `KAORI_LDAP_BIND_PASSWORD`, `KAORI_APP_ENV_FILE`, `KAORI_SECRETS_ENV_FILE`, `KAORI_POSTGRES_ADMIN_ENV_FILE`, `KAORI_POSTGRES_MIGRATION_ENV_FILE`, `KAORI_ACTIVE_RELEASE_ENV_FILE`, `KAORI_BUNDLED_FRESH_BOOTSTRAP`, `KAORI_BUNDLED_SCHEMA_CUTOVER`, `KAORI_POSTGRES_IMAGE`, `KAORI_REDIS_IMAGE`, `POSTGRES_PASSWORD`, `KAORI_DB_MIGRATION_URL`, `BAO_PG_CONNECTION_URL`.

## Verified code-level dependency observations

Readback at `kaori/staging@e1be7b01223df13ca3690ed0b361f4622bf33ee0`. This is bounded static
source evidence, not a live effective-configuration audit. References
are repository-relative source paths; line positions may move.

| Configuration | Confirmed implementation reference | Migration constraint |
| --- | --- | --- |
| SECRET_KEY | app/config/default.py:116 | Application config loading; session/signing consumers still require full trace |
| INTEGRATION_CREDENTIAL_KEY, INTEGRATION_CREDENTIAL_PREVIOUS_KEYS | app/config/default.py:131-135; app/security/credentials.py:23-30 | Encryption code reads app config or ENV outside application context; preserve key history and verify both contexts |
| DATABASE_URL | app/config/default.py:140; scripts/server_migrate_db.sh:19 | Runtime configuration and migration-only override must remain distinct |
| REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND | app/config/default.py:145-156, 285-286 | Broker and result backend fall back to REDIS_URL when explicit settings are absent; preserve independent effective URLs and coordinate rotation |
| RATELIMIT_STORAGE_URI | app/config/default.py:484-485 | Config declaration confirmed; rate limiter initialization needs further tracing |
| REDIS_PASSWORD | deploy/server/compose.server.yml | Redis command and health check consume the shared secrets file; keep independent service bootstrap |
| REPORT_S3_ACCESS_KEY_ID, REPORT_S3_SECRET_ACCESS_KEY | app/config/default.py:763-764; app/reports/storage/s3.py:81-82 | Report storage uses application config |
| ARCHIVE_S3_ACCESS_KEY_ID, ARCHIVE_S3_SECRET_ACCESS_KEY | app/config/default.py:630-634 | Existing per-field fallback to report credentials; review effective credential pairs before introducing independent archive scope |
| ADMIN_PASSWORD | app/commands/admin.py:72, 130 | Bootstrap and reset paths consume ENV; separate privileged lifecycle, do not change existing behavior here |
| RESOLVER_TOKEN_SIGNING_KEY | app/config/default.py:275; app/integrations/resolver_bootstrap.py:105-107 | Enabled resolver actions require a signing value with minimum length; preserve startup validation and review rotation |
| POSTGRES_PASSWORD | deploy/server/compose.server.yml | Admin env file delivered to PostgreSQL and provisioning; actual image-level consumer outside app |
| KAORI_DB_MIGRATION_URL | scripts/server_migrate_db.sh:9-19 | Explicit foreground migration subprocess override, not general runtime URL |
| BAO_PG_CONNECTION_URL | deploy/server/secret-store/openbao.hcl.example; secret-store.env.example | Candidate provider storage dependency, independent of OpenBao contents; actual pinned provider startup not tested |

The fallback observations are **existing behavior**, not authorization
for new fallback across Secret Store scopes. Before a future cutover,
resolve explicit versus inherited settings, validate complete credential
pairs and establish independently approved rollback. Do not remove or
alter existing fallback in this documentation increment.

LDAP and Google/GitHub SSO ENV names remain inventory entries with
candidate ownership, not verified direct code consumers: the inspected
identity-provider credential/configuration/browser files did not contain
those literal names. Trace canonical registry, database-backed provider
configuration and any compatibility ENV mapping separately; do not infer
that these variables are active or obsolete from this bounded search.
Full dependency mapping (including all 221 application settings),
restart/rotation and runtime proof remain outstanding.

## Remaining acceptance

Review exact consuming code, owners, generation/restart requirements and
protected workflow references beyond this bounded source set. Review
candidate scope names and independently approve policy before implementing
apply. Synthetic fixture and recovery UAT remain mandatory; this document
does not authorize changing any ENV, provider, database or deployment.
