from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from app.integrations.prometheus.scope import KUBERNETES_CLUSTER_SCOPE


@dataclass(frozen=True, slots=True)
class BindingProbe:
    metric: str
    label: str


@dataclass(frozen=True, slots=True)
class BindingValidationProfile:
    asset_type: str
    profile_key: str
    label: str
    probes: tuple[BindingProbe, ...]
    no_match_message: str
    consumer_family: str = 'metrics'


_PROFILES: dict[str, BindingValidationProfile] = {}
_LOCK = RLock()


def register_binding_validation_profile(
    profile: BindingValidationProfile,
    *,
    replace: bool = False,
) -> None:
    asset_type = str(profile.asset_type or '').strip()
    profile_key = str(profile.profile_key or '').strip()
    if not asset_type:
        raise ValueError('Prometheus binding validation profile requires an asset_type.')
    if not profile_key:
        raise ValueError('Prometheus binding validation profile requires a profile_key.')
    if not profile.probes:
        raise ValueError(f'Prometheus binding validation profile {asset_type!r} requires at least one probe.')
    with _LOCK:
        if asset_type in _PROFILES and not replace:
            raise ValueError(f'Prometheus binding validation profile {asset_type!r} is already registered.')
        _PROFILES[asset_type] = profile


def get_binding_validation_profile(asset_type: str) -> BindingValidationProfile | None:
    return _PROFILES.get(str(asset_type or '').strip())


def registered_binding_validation_profiles() -> tuple[BindingValidationProfile, ...]:
    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


register_binding_validation_profile(
    BindingValidationProfile(
        asset_type=KUBERNETES_CLUSTER_SCOPE,
        profile_key='kubernetes-metrics-v1',
        label='Kubernetes Metrics v1',
        probes=(
            BindingProbe('kube_node_info', 'Kubernetes node identity'),
            BindingProbe('kube_namespace_status_phase', 'Kubernetes namespace identity'),
            BindingProbe('kube_pod_info', 'Kubernetes pod identity'),
        ),
        no_match_message=(
            'The selector was accepted, but no scoped kube-state-metrics identity series matched. '
            'Verify the selector label/value on kube_node_info, kube_namespace_status_phase, or kube_pod_info.'
        ),
    )
)
