from __future__ import annotations

from sqlalchemy import func

from app.extensions.db import db
from app.models.intelligence import IntelligenceExecutionJournal


def verification_outcome_counts() -> dict[str, int]:
    """Bounded, SQL-grouped verification evidence shared by Intelligence views.

    A successful resolver dispatch with failed post-action verification still
    requires operator attention; the journal remains authoritative and immutable.
    """
    state = IntelligenceExecutionJournal.result_json['verification']['status'].as_string()
    rows = (
        db.session.query(state, func.count(IntelligenceExecutionJournal.id))
        .filter(IntelligenceExecutionJournal.status == 'succeeded')
        .group_by(state)
        .all()
    )
    totals = {key: 0 for key in ('verified', 'pending', 'failed')}
    for status, count in rows:
        if status in totals:
            totals[status] += int(count or 0)
    return totals
