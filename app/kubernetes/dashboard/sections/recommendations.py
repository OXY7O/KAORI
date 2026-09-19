from __future__ import annotations

from app.intelligence.dashboard_recommendations import get_dashboard_recommendation_findings
from app.kubernetes.dashboard.schema import RecommendationItem
from app.kubernetes.dashboard.utils import recommendation_href, recommendation_icon


def build_recommendations(*, selected_cluster_id: str | None) -> list[RecommendationItem]:
    cards = get_dashboard_recommendation_findings(domain='kubernetes', asset_key=selected_cluster_id)

    return [
        RecommendationItem(
            title=str(card.get('title') or 'Review recommendation'),
            description=str(
                card.get('recommended_action')
                or card.get('summary')
                or 'Review the active finding in Intelligence > Recommendations.'
            ),
            category=str(card.get('category_label') or card.get('category') or 'Operations'),
            severity=str(card.get('severity') or 'info'),
            icon=recommendation_icon(card),
            href=recommendation_href(card),
            priority=str(card.get('priority') or 'P3'),
            source=str(card.get('signal_source_label') or card.get('signal_source') or 'Intelligence engine'),
            rule_key=str(card.get('rule_key') or ''),
        )
        for card in cards
    ]
