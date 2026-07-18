from app.prometheus.consumer import PrometheusConsumer


class AnalyticsPrometheusService:
    """Compatibility wrapper around the canonical Prometheus consumer facade."""

    def __init__(self, cluster):
        self.cluster = cluster
        self.consumer = PrometheusConsumer(cluster)

    def query(self, promql: str):
        return self.consumer.query(promql)

    def query_range(
        self,
        promql: str,
        start,
        end,
        step: str = '1h',
    ):
        return self.consumer.query_range(
            promql,
            start,
            end,
            step,
        )
