from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from kubernetes import client, config
from kubernetes.client import AppsV1Api, CoreV1Api, NetworkingV1Api, StorageV1Api


class KubernetesClient:
    def __init__(
        self,
        kubeconfig_content: str,
        *,
        verify_ssl: bool = True,
    ) -> None:
        self.kubeconfig_content = kubeconfig_content
        self.verify_ssl = verify_ssl

    def _load_configuration(
        self,
    ) -> client.Configuration:
        kubeconfig_path = self._write_temp_kubeconfig()

        configuration = client.Configuration()

        try:
            config.load_kube_config(
                config_file=str(
                    kubeconfig_path,
                ),
                client_configuration=configuration,
            )

            configuration.verify_ssl = self.verify_ssl

            if not self.verify_ssl:
                setattr(
                    configuration,
                    'assert_hostname',
                    False,
                )

                configuration.ssl_ca_cert = None

            return configuration

        finally:
            kubeconfig_path.unlink(
                missing_ok=True,
            )

    def _api_client(
        self,
    ) -> client.ApiClient:
        configuration = self._load_configuration()

        return client.ApiClient(
            configuration=configuration,
        )

    def core_api(
        self,
    ) -> CoreV1Api:
        return CoreV1Api(
            self._api_client(),
        )

    def apps_api(
        self,
    ) -> AppsV1Api:
        return AppsV1Api(
            self._api_client(),
        )

    def networking_api(
        self,
    ) -> NetworkingV1Api:
        return NetworkingV1Api(
            self._api_client(),
        )

    def storage_api(
        self,
    ) -> StorageV1Api:
        return StorageV1Api(
            self._api_client(),
        )

    def connect(
        self,
    ) -> CoreV1Api:
        return self.core_api()

    def _write_temp_kubeconfig(
        self,
    ) -> Path:
        with NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            delete=False,
            suffix='.yaml',
        ) as temp_file:
            temp_file.write(
                self.kubeconfig_content,
            )

            temp_file.flush()

            return Path(
                temp_file.name,
            )
