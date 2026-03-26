from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from investorcrew.models import SelfReview, SelfReviewRecommendation


def build_self_review(run_id: str, result_payload: dict[str, Any], prompt_snapshot: dict[str, str]) -> SelfReview:
    recommendations: list[SelfReviewRecommendation] = []

    missing_metrics = []
    diligence_packet = result_payload.get("diligence_packet") or {}
    stock_report = diligence_packet.get("stock_report") or {}
    economic_report = diligence_packet.get("economic_report") or {}
    classification = result_payload.get("classification") or {}
    votes = result_payload.get("votes") or []

    missing_metrics.extend(stock_report.get("missing_metrics") or [])
    missing_metrics.extend(item.replace("Missing metric: ", "") for item in (economic_report.get("open_unknowns") or []))

    if missing_metrics:
        recommendations.append(
            SelfReviewRecommendation(
                category="missing_metrics/data",
                priority="high",
                recommendation=f"Add or source the missing metrics earlier in the workflow: {', '.join(missing_metrics[:4])}.",
                rationale="Repeated missing metrics reduce conviction and trigger circular follow-up loops.",
            )
        )

    mixed_votes = sum(1 for vote in votes if vote.get("vote") == "mixed")
    if mixed_votes:
        recommendations.append(
            SelfReviewRecommendation(
                category="process/stage_changes",
                priority="medium",
                recommendation="Add a clearer confidence summary before proposal synthesis so mixed-conviction runs distinguish watchlist ideas from accumulation ideas.",
                rationale="The current proposal layer can look too supportive when the panel is mostly mixed.",
            )
        )

    if prompt_snapshot.get("investor_analysis"):
        recommendations.append(
            SelfReviewRecommendation(
                category="prompt_improvements",
                priority="medium",
                recommendation="Tune the investor-analysis prompt to force sharper final stances and explicit confidence levels.",
                rationale="The current six-stage structure is useful, but the final conclusion still clusters around similar language.",
            )
        )

    if classification.get("needs_technology_report") and classification.get("needs_stock_report"):
        recommendations.append(
            SelfReviewRecommendation(
                category="orchestration_changes",
                priority="medium",
                recommendation="Surface the technical diligence unknowns directly in the stock proposal risk block and investor falsification step.",
                rationale="Tech-heavy names need the technical and equity risks connected more explicitly in the final recommendation.",
            )
        )

    summary = (
        "Self-review found opportunities to sharpen missing-data handling, clarify mixed-conviction outcomes, "
        "and make the prompt stack more explicit in how it separates speculative from actionable ideas."
    )
    return SelfReview(
        review_id=str(uuid.uuid4()),
        run_id=run_id,
        summary=summary,
        recommendations=recommendations,
        created_at=datetime.now(UTC).isoformat(),
    )
