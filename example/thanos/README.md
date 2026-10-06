# Thanos Standalone Example

Start a standalone Thanos Query API:

```bash
cp example/.env.example example/.env
docker compose --env-file example/.env -f example/thanos/compose.yml up -d
curl --fail http://localhost:10902/-/ready
```

Standalone mode validates the Query API without a Store endpoint. Use `example/compose.demo.yml` when you want Thanos Query connected to a Prometheus Sidecar and MinIO object storage.
