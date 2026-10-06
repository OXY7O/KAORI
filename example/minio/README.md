# MinIO Standalone Example

```bash
cp example/.env.example example/.env
docker compose --env-file example/.env -f example/minio/compose.yml up -d
curl --fail http://localhost:9000/minio/health/ready
```

Demo credentials are intentionally non-production and live only in the example template. Use endpoint `http://localhost:9000`, access key `kaori-demo`, and secret key `kaori-demo-secret` when exercising KAORI Object Storage integration.

The pinned historical community image is a compatibility fixture, not production guidance. Override `MINIO_IMAGE` with an approved S3-compatible image when required.
