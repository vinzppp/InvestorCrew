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
    planning_draft = result_payload.get("planning_draft") or {}
    technical_reviews = result_payload.get("technical_review_rounds") or []
    final_disposition = result_payload.get("final_disposition") or "watchlist"
    committee_memo = result_payload.get("committee_memo") or {}

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
    pass_votes = sum(1 for vote in votes if vote.get("vote") == "pass")
    if mixed_votes or pass_votes:
        recommendations.append(
            SelfReviewRecommendation(
                category="process/stage_changes",
                priority="medium",
                recommendation="Keep sharpening the committee summary before proposal synthesis so mixed and pass-heavy panels separate watchlists from real investable setups.",
                rationale="The revised flow is more skeptical, but ambiguous runs still need a cleaner bridge into disposition and proposals.",
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
                recommendation="Surface the technical diligence unknowns directly in the committee conclusion, proposal risk block, and investor falsification step.",
                rationale="Tech-heavy names need the technical and equity risks connected more explicitly in the final recommendation.",
            )
        )

    if planning_draft.get("approval_warning") or any(not review.get("passes") for review in technical_reviews):
        recommendations.append(
            SelfReviewRecommendation(
                category="missing_metrics/data",
                priority="high",
                recommendation="Add better planning-stage sources or richer fixture research so the technical reviewer is not forced to gate on missing evidence.",
                rationale="Technology-heavy runs now depend on a real evidence trail, and the workflow should expose that need earlier.",
            )
        )

    if final_disposition == "no_invest":
        recommendations.append(
            SelfReviewRecommendation(
                category="prompt_improvements",
                priority="low",
                recommendation="Compare no-invest runs over time to see whether the planner and committee are appropriately conservative or over-blocking.",
                rationale="No-invest is a healthy outcome now, but it should be reviewed to confirm the bar is disciplined rather than excessively restrictive.",
            )
        )

    if committee_memo.get("weighing"):
        recommendations.append(
            SelfReviewRecommendation(
                category="process/stage_changes",
                priority="low",
                recommendation="Keep the committee weighing section explicit about which opportunity mattered most and which risk actually prevented higher conviction.",
                rationale="A readable committee memo is now the user-facing synthesis, so clarity here matters more than internal orchestration detail.",
            )
        )

    summary = (
        "Self-review found opportunities to sharpen missing-data handling, improve planning-stage sourcing, "
        "and make skeptical committee outcomes clearer when the panel or technical reviewer does not clear the action bar."
    )
    return SelfReview(
        review_id=str(uuid.uuid4()),
        run_id=run_id,
        summary=summary,
        recommendations=recommendations,
        created_at=datetime.now(UTC).isoformat(),
    )
