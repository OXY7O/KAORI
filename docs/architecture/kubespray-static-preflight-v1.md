# Kubespray self-managed static preflight — non-mutating candidate

Authority: #4800 under #4796/#556. Stage: implementation candidate for Developer Check and pre-admission review. **No external execution and no approved provisioning Plan**.

## Upstream qualifications

The pinned candidate is `kubernetes-sigs/kubespray` tag `v2.32.0`, verified tag commit `9751ea6f63244e433a7a6263d9ecf381e57bb8e9`, published 2026-09-22. Upstream release notes specify Kubernetes 1.36 as the default minor and Ansible 12 / ansible-core 2.19 (Kubespray release requirements include `ansible==12.3.0`). These are **source compatibility declarations**, not host/UAT success. Production compatibility must be qualified per exact OS, CNI, CRI and cluster versions in the future source/Execution Environment and native API UAT.

## Current static assessor

`app/infrastructure_automation/kubernetes/kubespray_preflight.py` accepts a **synthetic or already authorized** input shape with management type, non-production environment, exact upstream release+SHA, Kubernetes minor, pod/service CIDRs and three existing Linux assets (one control-plane, two workers). It rejects secret/unknown fields, unsupported managed Kubernetes provider, version drift, invalid/overlapping networks, duplicate assets/IPs, mismatched roles and below-minimum resources. Only narrow Oracle Linux 9 / Ubuntu 24.04 metadata is recognized for this pilot, although upstream Kubespray supports additional distributions.

The assessor never calls Ansible, checks host credentials, reads provider data, creates VM/cluster state or contacts Kubernetes. **Every static-success result is `requires_provider_evidence`**, never Ready-to-Run. Follow-up evidence (trusted host/SSH identity, real read-only facts, DNS/clock/ports, privilege authority, capacity/backups, immutable source/EE, human approval) must be supplied through a separately admitted KAORI Plan and approved execution path. The `inventory_fingerprint` is a deterministic correlation hint, **not an approval signature**.

There is no UI, persistence model, schema migration, execution task, or scheduled workflow. The existing Kubernetes Cluster/IntegrationBinding and canonical Jobs architecture remain authoritative.

## Developer Check

```bash
python -m ruff check app/infrastructure_automation/kubernetes tests/contracts/platform_operations/test_kubespray_static_preflight_contract.py
python -m ruff format --check app/infrastructure_automation/kubernetes tests/contracts/platform_operations/test_kubespray_static_preflight_contract.py
python -m pytest -q -p no:cacheprovider tests/contracts/platform_operations/test_kubespray_static_preflight_contract.py
```

A passing static unit test cannot substitute for existing-host provisioning preflight or real Kubernetes UAT. Keep infrastructure mutation, cluster installation, node patching and managed Kubernetes control planes **HOLD** under #4801/#4802 and separate managed-provider authorities.
