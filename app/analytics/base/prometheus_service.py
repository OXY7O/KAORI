from app.prometheus.client import PrometheusClient


class AnalyticsPrometheusService:
    """
    Base service for all analytics modules.
    """

    def __init__(self, cluster):
        self.cluster = cluster
        self.client = PrometheusClient(cluster)

    def query(self, promql: str):
        return self.client.query(promql)

    def query_range(
        self,
        promql: str,
        start,
        end,
        step: str = '1h',
    ):
        return self.client.query_range(
            promql,
            start,
            end,
            step,
        )
