# Alertmanager Standalone Example

```bash
cp example/.env.example example/.env
docker compose --env-file example/.env -f example/alertmanager/compose.yml up -d
curl --fail http://localhost:9093/-/ready
```

Use `http://localhost:9093` as the KAORI Alertmanager integration endpoint. The receiver is intentionally null: the example demonstrates alert state/grouping/inhibition without sending notifications outside the disposable environment.
