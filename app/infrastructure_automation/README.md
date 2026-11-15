# Infrastructure Automation — guarded localhost worker pilot

Authority: #556, #4796, #4799, and OXY7O/kaori-operations#1. **Non-production read-only smoke only**. The operator-facing Ansible provider, remote SSH credentials, cluster create/upgrade/patch and production execution image are NOT implemented here.

## Review/UAT contract

- The immutable source revision is `OXY7O/kaori-operations@a182ddd04b353497021b3a089d3289128e999f78`. Its source manifest, playbook and localhost inventory are restricted to one allowlisted operation: `linux.host_facts.v1`.
- KAORI's existing `enqueue_canonical_job` dispatches a `JobExecution` through a **dedicated `automation` Celery queue**; worker concurrency 1. The task is in `app.infrastructure_automation.tasks`, not a synchronous Flask route.
- Both dispatch and execution **fail closed** unless `APP_ENV` is `development`/`testing` and `KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true`.
- Runner output is reduced to bounded Linux OS/kernel facts and a source SHA in committed JobExecution. Temporary Runner artifacts are deleted; **environment image attestation remains NOT VERIFIED**.
- There is no arbitrary host selector, SSH key, become, extra variables, Kubernetes mutation, schedule, or user-visible provisioning action.

## Guided Dev Container UAT (local host only)

1. On the approved Dev Container, clone `OXY7O/kaori-operations` into `/workspace/kaori-operations`, checkout exact SHA `a182ddd04b353497021b3a089d3289128e999f78`, and require `git status --porcelain` to be empty.
2. Install dependencies into the Dev Container test Python environment from `/workspace/kaori-operations/execution-environments/requirements.txt`. Never modify the production image during UAT.
3. Run normal KAORI PostgreSQL/Redis/app prerequisites. In its own terminal start the isolated automation worker with: `APP_ENV=development KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true celery --app celery_worker:celery_app worker --queues=automation --concurrency=1 --prefetch-multiplier=1 --loglevel=INFO --hostname=automation@%h`.
4. In a second terminal, invoke: `APP_ENV=development KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true flask --app run:app automation-localhost-probe --source-path /workspace/kaori-operations --source-sha a182ddd04b353497021b3a089d3289128e999f78`.
5. Review **Platform Operations → Jobs & Executions → Executions**. The new JobExecution must include the approved operation, immutable SHA, bounded OS/kernel facts, `changed=false`, and `environment_attestation=NOT VERIFIED`. Check worker log for no secret or raw event output.
6. Negative: disable the flag, provide an invalid SHA, dirty the Git checkout, or stop the automation worker; operation must be blocked and no false successful JobExecution created.
7. Record actual case IDs/commands/SHA, sanitized results and explicit Human Acceptance on issue #4799; stop the worker and disable the pilot flag afterward.

**Not a production-ready feature:** no remote provider identity, credential authority, image digest, trusted SSH inventory, managed Kubernetes capability or real infrastructure mutation. Do not treat localhost UAT as cluster provisioning evidence. See #4800–#4802 for subsequent gated workstreams.

## Focused pre-UAT quality checks (in existing Dev Container)

Run against this exact work-branch source before asking for Human UAT:

```bash
python -m ruff check app/infrastructure_automation app/commands/__init__.py app/config/default.py tests/contracts/platform_operations/test_ansible_localhost_worker_contract.py
python -m ruff format --check app/infrastructure_automation/*.py app/commands/__init__.py app/config/default.py tests/contracts/platform_operations/test_ansible_localhost_worker_contract.py
python -m pytest -q -p no:cacheprovider tests/contracts/platform_operations/test_ansible_localhost_worker_contract.py
```

Optional **image build-only** smoke (no deployment/runner execution) for the isolated pinned worker target:
`docker build --target automation-worker --tag kaori-automation-worker:uat .`

The default Dockerfile final target remains `production`; this opt-in `automation-worker` target is not part of current production Compose services. A successful build is not equivalent to runtime/Dev Container/real-provider UAT. Record all command results, SHA, environment and any blocker; do not mark NOT RUN as PASS.
