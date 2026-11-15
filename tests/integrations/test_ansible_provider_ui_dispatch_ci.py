"""Ephemeral CI full HTTP -> canonical Celery -> Ansible -> Postgres proof (#4817).

Requires a running 'automation' Celery worker and explicitly opted-in testing env.
No real remote hosts, SSH secrets or Kubernetes APIs are involved.
"""
from __future__ import annotations

import re
from time import monotonic, sleep
from uuid import uuid4

from app import create_app
from app.extensions.db import db
from app.infrastructure_automation.source import SOURCE_SHA
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.user import User

ROOT = '/integrations/orchestration/ansible/'


def _form_token(page_html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', page_html)
    assert match, 'Actual form did not render a CSRF token'
    return match.group(1)


def test_real_http_form_enqueues_scoped_read_only_runner_evidence() -> None:
    app = create_app('testing')
    identity = uuid4().hex[:12]
    name = f'Ansible CI Pilot {identity}'

    with app.app_context():
        operator = User(
            username=f'ui-ci-{identity}',
            email=f'ui-ci-{identity}@example.invalid',
            auth_source='database',
            is_super_admin=True,
            account_is_active=True,
        )
        operator.set_password('Synthetic-UAT-Only-Identity-Secret')
        db.session.add(operator)
        db.session.commit()
        user_id = operator.id
        session_id = operator.get_id()

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = session_id
        session['_fresh'] = True
        session['auth_source'] = 'database'

    overview = client.get('/integrations/orchestration')
    assert overview.status_code == 200
    assert b'Infrastructure Automation' in overview.data

    form = client.get(f'{ROOT}instances/new')
    assert form.status_code == 200
    creation = client.post(
        f'{ROOT}instances/new',
        data={
            'csrf_token': _form_token(form.get_data(as_text=True)),
            'name': name,
            'description': 'CI worker localhost verification only',
            'environment': 'testing',
            'enabled': 'on',
        },
    )
    assert creation.status_code in {302, 303}

    with app.app_context():
        connection = IntegrationInstance.query.filter_by(
            integration_type='infrastructure_automation', provider_key='ansible', name=name
        ).one()
        instance_id = connection.id
        assert connection.readiness_status == 'validation_required'

    detail_url = f'{ROOT}instances/{instance_id}'
    detail = client.get(detail_url)
    assert detail.status_code == 200
    assert b'Run Local Read-only Test' in detail.data

    action = client.post(
        f'{detail_url}/probe',
        data={'csrf_token': _form_token(detail.get_data(as_text=True))},
    )
    assert action.status_code in {302, 303}

    with app.app_context():
        deadline = monotonic() + 100
        while monotonic() < deadline:
            db.session.expire_all()
            job = (
                JobExecution.query.filter_by(
                    integration_type='infrastructure_automation',
                    integration_instance_id=instance_id,
                    operation='automation_localhost_host_facts',
                )
                .order_by(JobExecution.id.desc())
                .first()
            )
            if job is not None and job.is_terminal:
                assert job.status == 'succeeded', f'Failed canonical lifecycle: {job.status}'
                result = job.result_summary_json or {}
                assert result.get('source_sha') == SOURCE_SHA
                assert result.get('target') == 'automation-worker:localhost'
                assert result.get('changed') is False
                assert result.get('environment_attestation') == 'NOT VERIFIED'
                facts = result.get('facts') or {}
                assert facts.get('ansible_distribution')
                assert facts.get('ansible_kernel')
                assert job.queue_name == 'automation'
                assert job.requested_by_user_id == user_id
                break
            sleep(1)
        else:
            raise AssertionError('UI-triggered canonical JobExecution never reached a terminal state')

    rendered = client.get(detail_url)
    assert rendered.status_code == 200
    assert b'Read-only Execution Evidence' in rendered.data
    assert b'OS Distribution' in rendered.data
    assert b'No Changes' in rendered.data
    assert b'Not Verified' in rendered.data
    # Human-facing UI never implies the local test verified an external host.
    with app.app_context():
        connection = db.session.get(IntegrationInstance, instance_id)
        assert connection is not None
        assert connection.readiness_status == 'validation_required'
    print('KAORI UI FULL INTEGRATION PASS: form -> Celery -> Runner -> committed scoped evidence -> rendered detail')
