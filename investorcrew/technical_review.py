from __future__ import annotations

from investorcrew.models import PlanningDraft, TechnicalDueDiligenceReport, TechnicalReviewRound


def review_technical_report(
    report: TechnicalDueDiligenceReport,
    planning_draft: PlanningDraft,
    round_index: int,
) -> TechnicalReviewRound:
    findings: list[str] = []
    required_revisions: list[str] = []

    depth_signals = [
        report.scientific_mechanism,
        report.proof_status,
        report.feasibility,
        report.cost_curve,
        report.timeline,
        report.regulatory_path,
        report.capital_intensity,
    ]
    depth_score = round(sum(1 for signal in depth_signals if signal and "unknown" not in signal.lower()) / len(depth_signals), 2)

    citation_count = len(report.citations)
    evidence_quality_score = round(min(1.0, citation_count / 3), 2)

    feasibility_score = 0.35
    if report.engineering_bottlenecks:
        feasibility_score += 0.2
    if report.failure_modes:
        feasibility_score += 0.2
    if "regulatory" in report.regulatory_path.lower() or "licensed" in report.regulatory_path.lower():
        feasibility_score += 0.15
    if "cost" in report.cost_curve.lower() or "capital" in report.capital_intensity.lower():
        feasibility_score += 0.1
    feasibility_reasoning_score = round(min(1.0, feasibility_score), 2)

    competitive_analysis_score = round(min(1.0, len(report.competitive_landscape) / 3), 2)
    clarity_signals = [
        report.summary,
        report.preferred_rationale,
        report.timeline,
        report.regulatory_path,
    ]
    clarity_score = round(sum(1 for signal in clarity_signals if len(signal.split()) >= 8) / len(clarity_signals), 2)

    if depth_score < 0.75:
        findings.append("The technical report is still too shallow for a frontier-technology investment decision.")
        required_revisions.append("Deepen the scientific mechanism, proof status, cost curve, and deployment timeline.")
    if evidence_quality_score < 0.65:
        findings.append("The report lacks enough source-backed support for a technology-heavy decision.")
        required_revisions.append("Add at least two credible sources or explain why the claim remains unverified.")
    if feasibility_reasoning_score < 0.75:
        findings.append("Feasibility is described, but the bottlenecks and failure paths are not decision-useful yet.")
        required_revisions.append("Make the bottlenecks, regulatory gating items, and failure modes more explicit.")
    if competitive_analysis_score < 0.65:
        findings.append("The competitive analysis is still underdeveloped.")
        required_revisions.append("Compare the technology against at least three relevant alternatives or substitute solutions.")
    if clarity_score < 0.75:
        findings.append("The report needs clearer synthesis before it goes to the investor panel.")
        required_revisions.append("Tighten the summary and preferred-rationale sections so the edge and risks are obvious.")

    overall_score = round(
        (
            depth_score * 0.28
            + evidence_quality_score * 0.26
            + feasibility_reasoning_score * 0.22
            + competitive_analysis_score * 0.14
            + clarity_score * 0.10
        ),
        2,
    )
    passes = overall_score >= 0.72 and not required_revisions
    blocked = round_index >= 3 and not passes

    summary = (
        f"Technical review round {round_index} scored {overall_score:.2f}. "
        f"Primary strategy is {planning_draft.primary_strategy}, and the reviewer {'passed' if passes else 'requested revisions'} the report."
    )

    return TechnicalReviewRound(
        round_index=round_index,
        passes=passes,
        blocked=blocked,
        overall_score=overall_score,
        depth_score=depth_score,
        evidence_quality_score=evidence_quality_score,
        feasibility_reasoning_score=feasibility_reasoning_score,
        competitive_analysis_score=competitive_analysis_score,
        clarity_score=clarity_score,
        summary=summary,
        findings=findings,
        required_revisions=required_revisions,
    )


def strengthen_technical_report(
    report: TechnicalDueDiligenceReport,
    planning_draft: PlanningDraft,
    review_round: TechnicalReviewRound,
) -> TechnicalDueDiligenceReport:
    citations = list(report.citations)
    source_titles = ", ".join(source.title for source in citations[:3]) if citations else "available sources"

    improved_mechanism = report.scientific_mechanism
    if "unknown" in improved_mechanism.lower():
        improved_mechanism = (
            f"The core mechanism should be evaluated through {planning_draft.primary_strategy}, with attention to whether the claimed system can convert design theory into a repeatable commercial result."
        )

    improved_proof = report.proof_status
    if "unknown" in improved_proof.lower():
        improved_proof = (
            f"Existing evidence is partial rather than definitive; the strongest source-backed checkpoints currently come from {source_titles}."
        )

    bottlenecks = list(report.engineering_bottlenecks)
    if len(bottlenecks) < 3:
        bottlenecks.extend(
            [
                "Scale-up execution between pilot evidence and commercial deployment",
                "Supplier or manufacturing constraints during first production ramps",
                "Regulatory or customer qualification timing before revenue conversion",
            ][: 3 - len(bottlenecks)]
        )

    failure_modes = list(report.failure_modes)
    if len(failure_modes) < 3:
        failure_modes.extend(
            [
                "The technology works in principle but misses commercial cost targets",
                "Licensing, qualification, or deployment timing slips enough to force dilutive financing",
                "A simpler incumbent or adjacent technology solves the customer problem first",
            ][: 3 - len(failure_modes)]
        )

    regulatory_path = report.regulatory_path
    if "unknown" in regulatory_path.lower():
        regulatory_path = (
            "Regulatory gating remains material and should be treated as a first-order milestone rather than a background assumption."
        )

    timeline = report.timeline
    if "unknown" in timeline.lower():
        timeline = (
            "The timeline should be split into technical proof, qualification, financing, and commercial deployment gates rather than treated as one date."
        )

    cost_curve = report.cost_curve
    if "unknown" in cost_curve.lower():
        cost_curve = (
            "The cost curve is not yet fully proven; investors should focus on whether the first deployments can validate a path to competitive unit economics."
        )

    capital_intensity = report.capital_intensity
    if "unknown" in capital_intensity.lower():
        capital_intensity = (
            "Capital intensity appears material and should be framed around how much funding is required before self-sustaining revenue."
        )

    return TechnicalDueDiligenceReport(
        subject=report.subject,
        selected_dimensions=list(report.selected_dimensions),
        summary=f"{report.summary} Reviewer emphasis: {review_round.required_revisions[0] if review_round.required_revisions else 'Maintain current rigor.'}",
        what_it_is=report.what_it_is,
        world_impact=report.world_impact,
        scientific_mechanism=improved_mechanism,
        proof_status=improved_proof,
        feasibility=report.feasibility,
        engineering_bottlenecks=bottlenecks,
        requirements=list(report.requirements),
        constraints=list(report.constraints),
        competitive_landscape=list(report.competitive_landscape),
        preferred_technology=report.preferred_technology,
        preferred_rationale=(
            f"{report.preferred_rationale} This preference should only hold if the cited evidence continues to support the feasibility and deployment case."
        ),
        cost_curve=cost_curve,
        timeline=timeline,
        regulatory_path=regulatory_path,
        manufacturing_dependencies=list(report.manufacturing_dependencies),
        capital_intensity=capital_intensity,
        failure_modes=failure_modes,
        citations=citations,
        open_unknowns=list(report.open_unknowns),
    )
