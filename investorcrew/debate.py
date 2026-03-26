from __future__ import annotations

from investorcrew.data_store import KnowledgeBase
from investorcrew.diligence import apply_macro_supplemental_metrics, apply_stock_supplemental_metrics
from investorcrew.events import RunEventSink
from investorcrew.models import (
    CommitteeMemo,
    CompanyRecord,
    CrossExamination,
    DiscussionEntry,
    DueDiligencePacket,
    InfoRequest,
    InvestorAnalysis,
    InvestorProfile,
    PlanningDraft,
    Proposal,
    VoteRecord,
)
from investorcrew.providers import MacroDataClient, MarketDataClient


STRATEGY_EXPERTISE = {
    "warren_buffett": {"cash_flow_compounder": 1.0, "valuation_mispricing": 0.95, "inflation_resilience": 0.75, "tech_feasibility": 0.25, "macro_regime": 0.2, "market_winner": 0.45, "runway_and_financing": 0.35},
    "charlie_munger": {"cash_flow_compounder": 0.9, "valuation_mispricing": 0.75, "inflation_resilience": 0.6, "tech_feasibility": 0.45, "macro_regime": 0.25, "market_winner": 0.7, "runway_and_financing": 0.35},
    "ray_dalio": {"cash_flow_compounder": 0.4, "valuation_mispricing": 0.45, "inflation_resilience": 0.95, "tech_feasibility": 0.2, "macro_regime": 1.0, "market_winner": 0.35, "runway_and_financing": 0.55},
    "benjamin_graham": {"cash_flow_compounder": 0.7, "valuation_mispricing": 1.0, "inflation_resilience": 0.55, "tech_feasibility": 0.1, "macro_regime": 0.15, "market_winner": 0.2, "runway_and_financing": 0.2},
    "peter_lynch": {"cash_flow_compounder": 0.8, "valuation_mispricing": 0.7, "inflation_resilience": 0.45, "tech_feasibility": 0.45, "macro_regime": 0.25, "market_winner": 0.8, "runway_and_financing": 0.35},
    "howard_marks": {"cash_flow_compounder": 0.65, "valuation_mispricing": 0.8, "inflation_resilience": 0.75, "tech_feasibility": 0.3, "macro_regime": 0.65, "market_winner": 0.45, "runway_and_financing": 0.6},
    "george_soros": {"cash_flow_compounder": 0.2, "valuation_mispricing": 0.3, "inflation_resilience": 0.85, "tech_feasibility": 0.35, "macro_regime": 1.0, "market_winner": 0.55, "runway_and_financing": 0.4},
    "stanley_druckenmiller": {"cash_flow_compounder": 0.3, "valuation_mispricing": 0.45, "inflation_resilience": 0.85, "tech_feasibility": 0.45, "macro_regime": 1.0, "market_winner": 0.8, "runway_and_financing": 0.45},
    "john_templeton": {"cash_flow_compounder": 0.65, "valuation_mispricing": 0.9, "inflation_resilience": 0.65, "tech_feasibility": 0.25, "macro_regime": 0.45, "market_winner": 0.35, "runway_and_financing": 0.35},
    "cathie_wood": {"cash_flow_compounder": 0.35, "valuation_mispricing": 0.2, "inflation_resilience": 0.2, "tech_feasibility": 0.95, "macro_regime": 0.2, "market_winner": 1.0, "runway_and_financing": 0.65},
}


def _safe_metric(report: dict[str, float | int | None], key: str) -> float:
    value = report.get(key)
    if value is None:
        return 0.0
    return float(value)


def _stock_signals(packet: DueDiligencePacket) -> dict[str, float]:
    report = packet.stock_report
    if report is None:
        return {"valuation": 0.5, "quality": 0.45, "runway": 0.5, "risk": 0.5}

    descriptor = report.cheap_or_expensive.lower()
    valuation = 0.5
    if "cheap" in descriptor:
        valuation = 0.78
    elif "fair" in descriptor:
        valuation = 0.58
    elif "speculative" in descriptor or "pre-revenue" in descriptor:
        valuation = 0.25
    elif "expensive" in descriptor:
        valuation = 0.22

    quality = 0.35
    operating = report.operating_metrics
    balance = report.balance_sheet_metrics
    if _safe_metric(operating, "gross_margin_pct") >= 60:
        quality += 0.15
    if _safe_metric(operating, "operating_margin_pct") >= 20:
        quality += 0.15
    if _safe_metric(operating, "revenue_growth_pct") >= 15:
        quality += 0.15
    if _safe_metric(balance, "net_cash_billion") > 0 or _safe_metric(balance, "cash_billion") > 0.7:
        quality += 0.1

    runway = 0.55
    first_revenue_year = report.balance_sheet_metrics.get("first_revenue_expected_year") or report.valuation_metrics.get("first_revenue_expected_year")
    cash_billion = _safe_metric(balance, "cash_billion")
    if cash_billion >= 1.0:
        runway = 0.72
    elif cash_billion <= 0.25 and first_revenue_year:
        runway = 0.25
    elif cash_billion <= 0.5:
        runway = 0.38

    risk = 0.35 + 0.08 * len(report.open_unknowns)
    if "pre-revenue" in descriptor or "speculative" in descriptor:
        risk += 0.2
    if report.missing_metrics:
        risk += 0.1

    return {
        "valuation": max(0.0, min(1.0, valuation)),
        "quality": max(0.0, min(1.0, quality)),
        "runway": max(0.0, min(1.0, runway)),
        "risk": max(0.0, min(1.0, risk)),
    }


def _macro_signal(packet: DueDiligencePacket) -> float:
    report = packet.economic_report
    if report is None:
        return 0.5
    growth = report.core_metrics.get("gdp_nowcast_pct") or 0
    unemployment = report.core_metrics.get("unemployment_pct") or 0
    hy = report.core_metrics.get("high_yield_spread_bps") or 0
    score = 0.5
    if growth >= 2.0:
        score += 0.15
    elif growth <= 1.0:
        score -= 0.18
    if unemployment <= 4.2:
        score += 0.08
    elif unemployment >= 5:
        score -= 0.1
    if hy >= 450:
        score -= 0.18
    if report.open_unknowns:
        score -= 0.05
    return max(0.0, min(1.0, score))


def _technology_signal(packet: DueDiligencePacket) -> dict[str, float]:
    report = packet.technical_report
    if report is None:
        return {"feasibility": 0.45, "impact": 0.5, "evidence": 0.35, "risk": 0.55}

    feasibility = 0.45
    lowered_feasibility = report.feasibility.lower()
    if "high" in lowered_feasibility or "already deployed" in lowered_feasibility:
        feasibility = 0.82
    elif "moderate" in lowered_feasibility or "plausible" in lowered_feasibility:
        feasibility = 0.58
    elif "low" in lowered_feasibility or "uncertain" in lowered_feasibility:
        feasibility = 0.28

    impact = 0.45
    world_impact = report.world_impact.lower()
    if "reshape" in world_impact or "24/7" in world_impact or "accelerate" in world_impact or "firm" in world_impact:
        impact = 0.78

    evidence = min(1.0, 0.25 + 0.12 * len(report.citations))
    risk = min(1.0, 0.25 + 0.1 * len(report.constraints) + 0.08 * len(report.open_unknowns))

    return {
        "feasibility": feasibility,
        "impact": impact,
        "evidence": evidence,
        "risk": risk,
    }


def _expertise_weight(profile: InvestorProfile, planning_draft: PlanningDraft) -> float:
    mapping = STRATEGY_EXPERTISE[profile.slug]
    strategies = [planning_draft.primary_strategy, *planning_draft.secondary_strategies]
    if not strategies:
        return 0.5
    return sum(mapping.get(strategy, 0.4) for strategy in strategies) / len(strategies)


def _philosophy_fit(profile: InvestorProfile, packet: DueDiligencePacket, planning_draft: PlanningDraft, stock: dict[str, float], tech: dict[str, float], macro: float) -> float:
    expertise = _expertise_weight(profile, planning_draft)
    fit = expertise * 0.55
    if planning_draft.primary_strategy == "cash_flow_compounder":
        fit += stock["quality"] * 0.25 + stock["valuation"] * 0.1
    elif planning_draft.primary_strategy == "valuation_mispricing":
        fit += stock["valuation"] * 0.3
    elif planning_draft.primary_strategy == "macro_regime":
        fit += macro * 0.35
    elif planning_draft.primary_strategy == "tech_feasibility":
        fit += tech["feasibility"] * 0.25 + tech["evidence"] * 0.15
    elif planning_draft.primary_strategy == "market_winner":
        fit += tech["impact"] * 0.2 + stock["quality"] * 0.15
    elif planning_draft.primary_strategy == "runway_and_financing":
        fit += stock["runway"] * 0.25 + (1 - stock["risk"]) * 0.1
    return max(0.0, min(1.0, fit))


def _evidence_quality(packet: DueDiligencePacket, stock: dict[str, float], tech: dict[str, float], macro: float) -> float:
    score = 0.45
    if packet.stock_report and not packet.stock_report.missing_metrics:
        score += 0.18
    elif packet.stock_report and len(packet.stock_report.missing_metrics) <= 2:
        score += 0.08
    if packet.technical_report:
        score += tech["evidence"] * 0.22
    if packet.economic_report:
        score += max(0.0, macro - 0.4) * 0.12
    if packet.industry_report:
        score += 0.08
    return max(0.0, min(1.0, score))


def _upside_case(packet: DueDiligencePacket, planning_draft: PlanningDraft, stock: dict[str, float], tech: dict[str, float], macro: float) -> float:
    if planning_draft.primary_strategy == "tech_feasibility":
        return max(0.0, min(1.0, 0.35 + tech["impact"] * 0.35 + tech["feasibility"] * 0.2 + stock["runway"] * 0.1))
    if planning_draft.primary_strategy == "market_winner":
        return max(0.0, min(1.0, 0.35 + tech["impact"] * 0.3 + stock["quality"] * 0.2 + stock["valuation"] * 0.15))
    if planning_draft.primary_strategy == "macro_regime":
        return max(0.0, min(1.0, 0.35 + macro * 0.45 + stock["valuation"] * 0.15))
    return max(0.0, min(1.0, 0.35 + stock["quality"] * 0.28 + stock["valuation"] * 0.22 + macro * 0.1))


def _downside_case(packet: DueDiligencePacket, planning_draft: PlanningDraft, stock: dict[str, float], tech: dict[str, float], macro: float) -> float:
    downside = stock["risk"] * 0.45 + (1 - stock["valuation"]) * 0.15 + (1 - macro) * 0.1
    if planning_draft.primary_strategy in {"tech_feasibility", "market_winner"}:
        downside += tech["risk"] * 0.3 + (1 - tech["feasibility"]) * 0.1
    if planning_draft.primary_strategy == "runway_and_financing":
        downside += (1 - stock["runway"]) * 0.2
    return max(0.0, min(1.0, downside))


def _final_stance(philosophy_fit: float, evidence_quality: float, upside: float, downside: float) -> str:
    net = 0.34 * philosophy_fit + 0.28 * evidence_quality + 0.28 * upside - 0.34 * downside
    if philosophy_fit < 0.42 or evidence_quality < 0.42:
        return "pass"
    if net >= 0.24 and downside <= 0.55:
        return "support"
    if net <= -0.08 or downside >= 0.72:
        return "oppose"
    return "mixed"


def _portfolio_stance(vote: str) -> str:
    if vote == "support":
        return "This fits as a deliberate position, but only after the highest-risk assumptions are budgeted honestly."
    if vote == "oppose":
        return "This should stay at zero weight unless the downside meaningfully improves."
    if vote == "pass":
        return "Do not force a position here; keep it off the active book until the evidence bar is genuinely met."
    return "Keep sizing small and conditional on new proof rather than current narrative momentum."


def _build_follow_up_requests(profile: InvestorProfile, packet: DueDiligencePacket) -> list[InfoRequest]:
    requests: list[InfoRequest] = []
    if packet.stock_report and packet.stock_report.missing_metrics:
        relevant = [metric for metric in packet.stock_report.missing_metrics if metric in profile.preferred_metrics]
        if not relevant:
            relevant = packet.stock_report.missing_metrics[:2]
        requests.append(
            InfoRequest(
                requestor=profile.name,
                team="stock",
                needed_metrics=relevant[:2],
                reason="These missing company metrics still matter for sizing, philosophy fit, or dilution risk.",
            )
        )
    if packet.economic_report and packet.economic_report.open_unknowns:
        needed = [item.replace("Missing metric: ", "") for item in packet.economic_report.open_unknowns[:1]]
        if needed:
            requests.append(
                InfoRequest(
                    requestor=profile.name,
                    team="macro",
                    needed_metrics=needed,
                    reason="A regime-sensitive investor still wants the missing macro metric before increasing conviction.",
                )
            )
    return requests


def build_investor_analysis(
    profile: InvestorProfile,
    packet: DueDiligencePacket,
    planning_draft: PlanningDraft,
) -> tuple[InvestorAnalysis, dict[str, float]]:
    stock = _stock_signals(packet)
    tech = _technology_signal(packet)
    macro = _macro_signal(packet)
    fit = _philosophy_fit(profile, packet, planning_draft, stock, tech, macro)
    evidence = _evidence_quality(packet, stock, tech, macro)
    upside = _upside_case(packet, planning_draft, stock, tech, macro)
    downside = _downside_case(packet, planning_draft, stock, tech, macro)
    vote = _final_stance(fit, evidence, upside, downside)
    subject = packet.classification.company_name or "the opportunity"

    analysis = InvestorAnalysis(
        investor_name=profile.name,
        investor_slug=profile.slug,
        situation=(
            f"{profile.name} sees {'strong' if fit >= 0.7 else 'mixed' if fit >= 0.5 else 'weak'} philosophy fit. "
            f"{subject} is being judged through {planning_draft.primary_strategy.replace('_', ' ')} with a {profile.debate_role.lower()} lens."
        ),
        interpretation=(
            f"The evidence currently looks like valuation={stock['valuation']:.2f}, business quality={stock['quality']:.2f}, "
            f"technology evidence={tech['evidence']:.2f}, and macro support={macro:.2f}."
        ),
        thesis=(
            f"{profile.name} thinks the upside only works if {planning_draft.primary_strategy.replace('_', ' ')} holds in the real world rather than only in the narrative."
        ),
        falsification=(
            f"{profile.name} would abandon the idea if the key study questions break against the thesis, especially around "
            f"{planning_draft.key_study_questions[0].lower() if planning_draft.key_study_questions else 'the core underwriting assumption'}."
        ),
        portfolio=_portfolio_stance(vote),
        conclusion=(
            f"{profile.name} is {vote} because philosophy fit is {fit:.2f}, evidence quality is {evidence:.2f}, "
            f"upside is {upside:.2f}, and downside is {downside:.2f}."
        ),
        preliminary_vote=vote,
        follow_up_requests=_build_follow_up_requests(profile, packet),
    )
    return analysis, {
        "philosophy_fit": fit,
        "evidence_quality": evidence,
        "upside": upside,
        "downside": downside,
        "expertise": _expertise_weight(profile, planning_draft),
    }


def _aggregate_requests(analyses: list[InvestorAnalysis], team: str) -> list[str]:
    metrics: list[str] = []
    for analysis in analyses:
        for request in analysis.follow_up_requests:
            if request.team != team:
                continue
            for metric in request.needed_metrics:
                if metric not in metrics:
                    metrics.append(metric)
    return metrics


def _append_updates(
    analyses: list[InvestorAnalysis],
    team: str,
    supplied_metrics: list[str],
    missing_metrics: list[str],
    round_index: int,
) -> None:
    for analysis in analyses:
        relevant = []
        unresolved = []
        for request in analysis.follow_up_requests:
            if request.team != team:
                continue
            for metric in request.needed_metrics:
                if metric in supplied_metrics:
                    relevant.append(metric)
                if metric in missing_metrics:
                    unresolved.append(metric)
        if relevant:
            analysis.updates.append(
                f"Round {round_index}: {analysis.investor_name} received supplemental {team} data for {', '.join(relevant)}."
            )
        if unresolved:
            analysis.updates.append(
                f"Round {round_index}: {analysis.investor_name} still lacks {', '.join(unresolved)} and stays cautious."
            )


def build_cross_examination(
    analyses: list[InvestorAnalysis],
    planning_draft: PlanningDraft,
    evaluations: dict[str, dict[str, float]],
) -> list[CrossExamination]:
    bullish = [analysis for analysis in analyses if analysis.preliminary_vote == "support"]
    skeptical = [analysis for analysis in analyses if analysis.preliminary_vote in {"oppose", "pass"}]
    if not bullish or not skeptical:
        return []

    challenger = min(skeptical, key=lambda item: evaluations[item.investor_slug]["upside"] - evaluations[item.investor_slug]["downside"])
    respondent = max(bullish, key=lambda item: evaluations[item.investor_slug]["upside"] - evaluations[item.investor_slug]["downside"])
    key_question = planning_draft.key_study_questions[0] if planning_draft.key_study_questions else "the core risk-reward claim"
    return [
        CrossExamination(
            challenger=challenger.investor_name,
            respondent=respondent.investor_name,
            challenge=(
                f"{challenger.investor_name} argues that the bullish case has not yet earned confidence on {key_question.lower()}."
            ),
            response=(
                f"{respondent.investor_name} replies that the upside can still be attractive if milestone proof and customer evidence keep improving."
            ),
            committee_commentary=(
                f"The committee cares most about who addressed '{key_question}' with decision-useful evidence rather than louder conviction."
            ),
        )
    ]


def _stance_counts(analyses: list[InvestorAnalysis]) -> dict[str, int]:
    counts = {"support": 0, "mixed": 0, "oppose": 0, "pass": 0}
    for analysis in analyses:
        counts[analysis.preliminary_vote] += 1
    return counts


def _collect_opportunities(packet: DueDiligencePacket, planning_draft: PlanningDraft) -> list[str]:
    opportunities: list[str] = []
    if packet.technical_report:
        opportunities.append(packet.technical_report.world_impact)
        opportunities.append(packet.technical_report.preferred_rationale)
    if packet.stock_report:
        opportunities.append(packet.stock_report.cheap_or_expensive)
    if packet.industry_report:
        opportunities.extend(packet.industry_report.opportunities[:2])
    if packet.economic_report:
        opportunities.append(packet.economic_report.summary)
    deduped: list[str] = []
    for item in opportunities:
        cleaned = str(item).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    if not deduped:
        deduped.append(planning_draft.strategy_rationale)
    return deduped[:4]


def _collect_risks(packet: DueDiligencePacket) -> list[str]:
    risks: list[str] = []
    if packet.technical_report:
        risks.extend(packet.technical_report.failure_modes[:3])
        risks.extend(packet.technical_report.open_unknowns[:2])
    if packet.stock_report:
        risks.extend(packet.stock_report.open_unknowns[:3])
    if packet.industry_report:
        risks.extend(packet.industry_report.risks[:2])
    if packet.economic_report:
        risks.extend(packet.economic_report.open_unknowns[:2])
    deduped: list[str] = []
    for item in risks:
        cleaned = str(item).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped[:5] or ["Execution risk still dominates the current underwriting case."]


def build_committee_output(
    packet: DueDiligencePacket,
    planning_draft: PlanningDraft,
    analyses: list[InvestorAnalysis],
    cross_examinations: list[CrossExamination],
) -> tuple[CommitteeMemo, list[str], list[DiscussionEntry], list[Proposal], str]:
    counts = _stance_counts(analyses)
    support = counts["support"]
    mixed = counts["mixed"]
    oppose = counts["oppose"]
    passed = counts["pass"]
    company_name = packet.classification.company_name or "the idea"

    opportunities = _collect_opportunities(packet, planning_draft)
    risks = _collect_risks(packet)

    if support >= 5 and (oppose + passed) <= 2:
        disposition = "invest"
        conclusion = f"The committee thinks {company_name} is investable now, but only with disciplined sizing and milestone-based follow-through."
    elif support + mixed >= 5 and oppose <= 3:
        disposition = "watchlist"
        conclusion = f"The committee sees enough merit to keep {company_name} on an active watchlist, but not enough to underwrite full conviction today."
    else:
        disposition = "no_invest"
        conclusion = f"The committee does not think {company_name} clears the evidence and philosophy-fit bar today."

    weighing = (
        f"The committee weighed the case as {support} support, {mixed} mixed, {oppose} oppose, and {passed} pass. "
        f"It emphasized {planning_draft.primary_strategy.replace('_', ' ')} first, then checked whether the evidence, financing path, and downside matched that framing."
    )
    thesis = (
        f"The thesis is that {planning_draft.primary_strategy.replace('_', ' ')} either works well enough to justify the equity case or fails in a way that should keep capital on the sidelines."
    )
    memo = CommitteeMemo(
        thesis=thesis,
        opportunities=opportunities,
        risks=risks,
        weighing=weighing,
        conclusion=conclusion,
        disposition=disposition,
    )

    reasoning = [
        planning_draft.strategy_rationale,
        f"The committee used the planning stack of {planning_draft.primary_strategy} plus {', '.join(planning_draft.secondary_strategies) if planning_draft.secondary_strategies else 'no secondary lens'}.",
        weighing,
    ]

    discussion_log: list[DiscussionEntry] = []
    if cross_examinations:
        for exchange in cross_examinations:
            discussion_log.extend(
                [
                    DiscussionEntry(
                        speaker=exchange.challenger,
                        role="Investor Panel",
                        section="Challenge",
                        content=exchange.challenge,
                    ),
                    DiscussionEntry(
                        speaker=exchange.respondent,
                        role="Investor Panel",
                        section="Response",
                        content=exchange.response,
                    ),
                    DiscussionEntry(
                        speaker="Investment Committee",
                        role="Committee",
                        section="Committee Note",
                        content=exchange.committee_commentary,
                    ),
                ]
            )
    else:
        discussion_log.append(
            DiscussionEntry(
                speaker="Investment Committee",
                role="Committee",
                section="Committee Note",
                content="The panel did not split sharply enough to trigger a formal cross-examination, so the committee relied on the written investor analyses and follow-up requests.",
            )
        )

    discussion_log.append(
        DiscussionEntry(
            speaker="Investment Committee",
            role="Committee",
            section="Final Discussion",
            content=weighing,
        )
    )

    proposals: list[Proposal] = []
    if disposition != "no_invest":
        proposals.append(
            Proposal(
                proposal_id="P1",
                title=f"{'Accumulate' if disposition == 'invest' else 'Watchlist'} {company_name}",
                action="Build a position only if the decisive milestones keep confirming the thesis" if disposition == "invest" else "Monitor the idea and wait for better proof or a better price",
                thesis=thesis,
                horizon="12-36 months" if packet.stock_report else "6-18 months",
                key_drivers=planning_draft.key_study_questions[:3] or opportunities[:3],
                key_risks=risks[:3],
                portfolio_note="Keep position size tied to evidence quality rather than narrative intensity.",
            )
        )
        if packet.stock_report:
            proposals.append(
                Proposal(
                    proposal_id="P2",
                    title=f"Gate adds in {company_name} behind proof",
                    action="Only add capital after the next important milestone or evidence checkpoint is met",
                    thesis="The committee wants milestone discipline before conviction expands.",
                    horizon="Next 2-4 quarters",
                    key_drivers=planning_draft.key_study_questions[:3],
                    key_risks=risks[:3],
                    portfolio_note="Use this as the discipline proposal rather than the core alpha thesis.",
                )
            )
        if packet.economic_report and len(proposals) < 3:
            proposals.append(
                Proposal(
                    proposal_id=f"P{len(proposals) + 1}",
                    title="Respect the macro backdrop",
                    action="Budget exposure against current market and financing conditions",
                    thesis=packet.economic_report.summary,
                    horizon="Current regime",
                    key_drivers=["Macro conditions", "Credit and valuation conditions", "Market breadth"],
                    key_risks=["Regime change", "Valuation compression"],
                    portfolio_note="This proposal keeps the idea connected to the broader market backdrop.",
                )
            )

    return memo, reasoning[:3], discussion_log, proposals[:3], disposition


def build_votes(analyses: list[InvestorAnalysis], proposals: list[Proposal]) -> list[VoteRecord]:
    votes: list[VoteRecord] = []
    for proposal in proposals:
        title = proposal.title.lower()
        action = proposal.action.lower()
        for analysis in analyses:
            stance = analysis.preliminary_vote
            if "watchlist" in title or "monitor" in action:
                vote = "support" if stance in {"mixed", "oppose", "pass"} else "mixed"
            elif "gate adds" in title or "milestone" in action or "respect the macro" in title:
                vote = "support" if stance in {"mixed", "oppose", "pass"} else "mixed"
            else:
                vote = stance
            votes.append(
                VoteRecord(
                    proposal_id=proposal.proposal_id,
                    investor_name=analysis.investor_name,
                    vote=vote,
                    rationale=f"{analysis.investor_name} votes {vote} because {analysis.conclusion.lower()}",
                )
            )
    return votes


def run_investor_debate(
    knowledge_base: KnowledgeBase,
    investors: list[InvestorProfile],
    packet: DueDiligencePacket,
    planning_draft: PlanningDraft,
    company: CompanyRecord | None,
    market_data_client: MarketDataClient,
    macro_data_client: MacroDataClient,
    event_sink: RunEventSink | None = None,
) -> tuple[
    list[InvestorAnalysis],
    list[CrossExamination],
    CommitteeMemo,
    list[str],
    list[DiscussionEntry],
    list[Proposal],
    list[VoteRecord],
    int,
    str,
]:
    analyses: list[InvestorAnalysis] = []
    evaluations: dict[str, dict[str, float]] = {}
    profiles_by_slug = {profile.slug: profile for profile in investors}
    rounds_used = 0

    for profile in investors:
        analysis, scorecard = build_investor_analysis(profile, packet, planning_draft)
        analyses.append(analysis)
        evaluations[profile.slug] = scorecard

    if event_sink:
        for analysis in analyses:
            event_sink.record_dataclass(
                stage="investor_analysis",
                event_type="analysis",
                title=f"{analysis.investor_name} completed the six-stage analysis",
                payload=analysis,
                actor=analysis.investor_name,
            )

    for round_index in range(1, 3):
        stock_requests = _aggregate_requests(analyses, "stock")
        macro_requests = _aggregate_requests(analyses, "macro")
        if not stock_requests and not macro_requests:
            break
        rounds_used = round_index

        if event_sink and stock_requests:
            event_sink.record(
                stage="follow_up",
                event_type="request",
                title=f"Round {round_index} stock follow-up requested",
                payload={"team": "stock", "metrics": stock_requests, "round": round_index},
                actor="moderator",
            )
        if event_sink and macro_requests:
            event_sink.record(
                stage="follow_up",
                event_type="request",
                title=f"Round {round_index} macro follow-up requested",
                payload={"team": "macro", "metrics": macro_requests, "round": round_index},
                actor="moderator",
            )

        if packet.stock_report and company and stock_requests:
            supplied = apply_stock_supplemental_metrics(
                knowledge_base=knowledge_base,
                company=company,
                report=packet.stock_report,
                market_data_client=market_data_client,
                requested_metrics=stock_requests,
            )
            packet.supplemental_notes.append(
                f"Round {round_index} stock follow-up requested {', '.join(stock_requests)}; supplied {', '.join(supplied) if supplied else 'none'}."
            )
            if event_sink:
                event_sink.record(
                    stage="follow_up",
                    event_type="response",
                    title=f"Round {round_index} stock follow-up response",
                    payload={
                        "team": "stock",
                        "requested_metrics": stock_requests,
                        "supplied_metrics": supplied,
                        "remaining_missing": packet.stock_report.missing_metrics,
                    },
                    actor="stock_diligence",
                )
            _append_updates(analyses, "stock", supplied, packet.stock_report.missing_metrics, round_index)

        if packet.economic_report and macro_requests:
            supplied = apply_macro_supplemental_metrics(
                report=packet.economic_report,
                macro_data_client=macro_data_client,
                requested_metrics=macro_requests,
            )
            remaining = [item.replace("Missing metric: ", "") for item in packet.economic_report.open_unknowns]
            packet.supplemental_notes.append(
                f"Round {round_index} macro follow-up requested {', '.join(macro_requests)}; supplied {', '.join(supplied) if supplied else 'none'}."
            )
            if event_sink:
                event_sink.record(
                    stage="follow_up",
                    event_type="response",
                    title=f"Round {round_index} macro follow-up response",
                    payload={
                        "team": "macro",
                        "requested_metrics": macro_requests,
                        "supplied_metrics": supplied,
                        "remaining_missing": remaining,
                    },
                    actor="macro_diligence",
                )
            _append_updates(analyses, "macro", supplied, remaining, round_index)

        refreshed_analyses: list[InvestorAnalysis] = []
        refreshed_evaluations: dict[str, dict[str, float]] = {}
        for analysis in analyses:
            updated_analysis, scorecard = build_investor_analysis(
                profiles_by_slug[analysis.investor_slug],
                packet,
                planning_draft,
            )
            updated_analysis.updates = list(analysis.updates)
            updated_analysis.follow_up_requests = _build_follow_up_requests(
                profiles_by_slug[analysis.investor_slug],
                packet,
            )
            refreshed_analyses.append(updated_analysis)
            refreshed_evaluations[analysis.investor_slug] = scorecard
        analyses = refreshed_analyses
        evaluations = refreshed_evaluations
        if event_sink:
            for analysis in analyses:
                event_sink.record_dataclass(
                    stage="investor_revision",
                    event_type="delta_revision",
                    title=f"{analysis.investor_name} revised the stance after round {round_index}",
                    payload=analysis,
                    actor=analysis.investor_name,
                )

    cross_examinations = build_cross_examination(analyses, planning_draft, evaluations)
    if event_sink:
        for exchange in cross_examinations:
            event_sink.record_dataclass(
                stage="cross_examination",
                event_type="exchange",
                title=f"{exchange.challenger} challenged {exchange.respondent}",
                payload=exchange,
                actor=exchange.challenger,
            )

    committee_memo, committee_reasoning, discussion_log, proposals, disposition = build_committee_output(
        packet=packet,
        planning_draft=planning_draft,
        analyses=analyses,
        cross_examinations=cross_examinations,
    )
    if event_sink:
        event_sink.record_dataclass(
            stage="committee",
            event_type="memo",
            title="Investment Committee completed the final synthesis",
            payload=committee_memo,
            actor="investment_committee",
        )
        for entry in discussion_log:
            event_sink.record_dataclass(
                stage="committee_discussion",
                event_type="discussion_entry",
                title=f"{entry.speaker} discussion entry",
                payload=entry,
                actor=entry.speaker,
            )
        if proposals:
            for proposal in proposals:
                event_sink.record_dataclass(
                    stage="proposal_synthesis",
                    event_type="proposal",
                    title=f"Investment Committee proposed {proposal.title}",
                    payload=proposal,
                    actor="investment_committee",
                )
        else:
            event_sink.record(
                stage="proposal_synthesis",
                event_type="no_invest",
                title="Investment Committee concluded no proposal clears the bar",
                payload={"disposition": disposition},
                actor="investment_committee",
            )

    votes = build_votes(analyses, proposals)
    if event_sink:
        for vote in votes:
            event_sink.record_dataclass(
                stage="voting",
                event_type="vote",
                title=f"{vote.investor_name} voted {vote.vote} on {vote.proposal_id}",
                payload=vote,
                actor=vote.investor_name,
            )

    return analyses, cross_examinations, committee_memo, committee_reasoning, discussion_log, proposals, votes, rounds_used, disposition
