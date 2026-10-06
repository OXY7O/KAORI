# Prometheus Standalone Example

Start only Prometheus:

```bash
cp example/.env.example example/.env
docker compose --env-file example/.env -f example/prometheus/compose.yml up -d
curl --fail http://localhost:9090/-/ready
```

Use `http://localhost:9090` as the KAORI Prometheus integration endpoint. The standalone configuration self-scrapes and loads a synthetic rule without requiring Alertmanager, MinIO, or Thanos.
