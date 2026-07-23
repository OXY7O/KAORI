from __future__ import annotations

import pytest
from flask import Flask

from app.notifications.service import pop_quick_action_feedback, queue_transient_feedback

pytestmark = pytest.mark.functional


def test_transient_feedback_is_queued_once_without_persistence() -> None:
    app = Flask(__name__)
    app.secret_key = 'test-secret'

    with app.test_request_context('/'):
        feedback = queue_transient_feedback(
            status='error',
            title='Report Download Unavailable',
            message='The report artifact is not available.',
            detail='Generate the PDF before downloading it.',
        )

        assert feedback['status'] == 'error'
        assert feedback['notification_saved'] is False
        assert pop_quick_action_feedback() == feedback
        assert pop_quick_action_feedback() is None
