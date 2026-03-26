from __future__ import annotations

from statistics import mean

from investorcrew.data_store import KnowledgeBase
from investorcrew.events import RunEventSink
from investorcrew.diligence import apply_macro_supplemental_metrics, apply_stock_supplemental_metrics
from investorcrew.models import (
    CompanyRecord,
    CrossExamination,
    DueDiligencePacket,
    InfoRequest,
    InvestorAnalysis,
    InvestorProfile,
    Proposal,
    VoteRecord,
)
from investorcrew.providers import MacroDataClient, MarketDataClient


PERSONA_WEIGHTS = {
    "warren_buffett": {"valuation": 1.7, "quality": 1.4, "macro": 0.4, "technology": 0.4},
    "charlie_munger": {"valuation": 1.3, "quality": 1.5, "macro": 0.5, "technology": 0.7},
    "ray_dalio": {"valuation": 0.7, "quality": 0.8, "macro": 1.7, "technology": 0.4},
    "benjamin_graham": {"valuation": 1.9, "quality": 0.9, "macro": 0.3, "technology": 0.2},
    "peter_lynch": {"valuation": 1.1, "quality": 1.2, "macro": 0.5, "technology": 0.8},
    "howard_marks": {"valuation": 1.4, "quality": 1.1, "macro": 0.9, "technology": 0.5},
    "george_soros": {"valuation": 0.5, "quality": 0.6, "macro": 1.8, "technology": 0.6},
    "stanley_druckenmiller": {"valuation": 0.7, "quality": 0.8, "macro": 1.9, "technology": 0.8},
    "john_templeton": {"valuation": 1.5, "quality": 1.0, "macro": 0.8, "technology": 0.5},
    "cathie_wood": {"valuation": 0.4, "quality": 1.0, "macro": 0.5, "technology": 1.8},
}


def _stock_signals(packet: DueDiligencePacket) -> dict[str, float]:
    report = packet.stock_report
    if report is None:
        return {"valuation": 0.0, "quality": 0.0}
    valuation = 0.0
    descriptor = report.cheap_or_expensive.lower()
    if "cheap" in descriptor:
        valuation = 0.8
    elif "expensive" in descriptor:
        valuation = -0.7
    elif "speculative" in descriptor:
        valuation = -0.6
    elif "pre-revenue" in descriptor:
        valuation = -0.4
    quality = 0.0
    if report.operating_metrics.get("gross_margin_pct", 0) >= 60:
        quality += 0.4
    if report.operating_metrics.get("operating_margin_pct", 0) >= 20:
        quality += 0.3
    if report.operating_metrics.get("revenue_growth_pct", 0) >= 10:
        quality += 0.3
    if report.balance_sheet_metrics.get("net_cash_billion", 0) > 0:
        quality += 0.2
    if report.balance_sheet_metrics.get("cet1_ratio_pct", 0) >= 12:
        quality += 0.2
    return {"valuation": valuation, "quality": min(quality, 1.0)}


def _macro_signal(packet: DueDiligencePacket) -> float:
    report = packet.economic_report
    if report is None:
        return 0.0
    growth = report.core_metrics.get("gdp_nowcast_pct", 0) or 0
    unemployment = report.core_metrics.get("unemployment_pct", 0) or 0
    hy = report.core_metrics.get("high_yield_spread_bps", 0) or 0
    score = 0.0
    if growth >= 2.0:
        score += 0.3
    elif growth <= 1.0:
        score -= 0.3
    if unemployment <= 4.2:
        score += 0.2
    if hy >= 450:
        score -= 0.4
    return max(min(score, 1.0), -1.0)


def _technology_signal(packet: DueDiligencePacket) -> float:
    report = packet.technical_report
    if report is None:
        return 0.0
    score = 0.0
    if "high" in report.feasibility.lower() or "already deployed" in report.feasibility.lower():
        score += 0.5
    if "reshape" in report.world_impact.lower() or "enables" in report.world_impact.lower():
        score += 0.3
    if len(report.constraints) >= 3:
        score -= 0.2
    return max(min(score, 1.0), -1.0)


def _preliminary_vote(score: float) -> str:
    if score >= 0.4:
        return "support"
    if score <= -0.4:
        return "oppose"
    return "mixed"


def _portfolio_stance(vote: str) -> str:
    if vote == "support":
        return "Use a measured but constructive size, adding only if thesis milestones continue to validate."
    if vote == "oppose":
        return "Keep sizing at zero or minimal until the thesis improves and the downside becomes more asymmetric."
    return "Treat this as a watchlist or starter position, not a full conviction allocation."


def _build_follow_up_requests(profile: InvestorProfile, packet: DueDiligencePacket) -> list[InfoRequest]:
    requests: list[InfoRequest] = []
    if packet.stock_report and packet.stock_report.missing_metrics:
        relevant = [metric for metric in packet.stock_report.missing_metrics if metric in profile.preferred_metrics]
        if not relevant and packet.stock_report.missing_metrics:
            relevant = packet.stock_report.missing_metrics[:1]
        if relevant:
            requests.append(
                InfoRequest(
                    requestor=profile.name,
                    team="stock",
                    needed_metrics=relevant[:2],
                    reason="These missing company metrics could materially change conviction and sizing.",
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
                    reason="The macro dashboard is missing a metric that informs regime risk.",
                )
            )
    return requests


def build_investor_analysis(profile: InvestorProfile, packet: DueDiligencePacket) -> InvestorAnalysis:
    stock_signals = _stock_signals(packet)
    macro_signal = _macro_signal(packet)
    technology_signal = _technology_signal(packet)
    weights = PERSONA_WEIGHTS[profile.slug]
    total_score = (
        stock_signals["valuation"] * weights["valuation"]
        + stock_signals["quality"] * weights["quality"]
        + macro_signal * weights["macro"]
        + technology_signal * weights["technology"]
    ) / sum(weights.values())
    vote = _preliminary_vote(total_score)
    subject = packet.classification.company_name or "the opportunity"
    metric_list = []
    for selection in packet.metric_selections:
        metric_list.extend(selection.chosen_metrics[:2])
    metric_summary = ", ".join(metric_list[:4]) if metric_list else "the core diligence packet"
    risks = packet.stock_report.open_unknowns if packet.stock_report else []
    if packet.economic_report:
        risks.extend(packet.economic_report.open_unknowns)
    if not risks:
        risks = ["No major missing metrics, but regime change risk always matters."]

    return InvestorAnalysis(
        investor_name=profile.name,
        investor_slug=profile.slug,
        situation=f"{profile.name} frames the situation around {metric_summary} and sees {subject} through a {profile.debate_role.lower()} lens.",
        interpretation=f"{profile.name} reads the evidence as quality={stock_signals['quality']:.1f}, valuation={stock_signals['valuation']:.1f}, technology={technology_signal:.1f}, macro={macro_signal:.1f}.",
        thesis=f"{profile.name}'s thesis is that {subject} can work if {profile.heuristics[0].lower()} and the selected diligence signals keep improving.",
        falsification=f"{profile.name} would change their mind if {risks[0].replace('Missing metric: ', '').lower()} breaks the expected case or if the downside stops being manageable.",
        portfolio=f"{_portfolio_stance(vote)} {profile.risk_rules[0]}",
        conclusion=f"{profile.name} is {vote} because {profile.philosophy.lower()}",
        preliminary_vote=vote,
        follow_up_requests=_build_follow_up_requests(profile, packet),
    )


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


def _append_updates(analyses: list[InvestorAnalysis], team: str, supplied_metrics: list[str], missing_metrics: list[str], round_index: int) -> None:
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
                f"Round {round_index}: {analysis.investor_name} still lacks {', '.join(unresolved)} and keeps some caution in the conclusion."
            )


def _vote_value(vote: str) -> int:
    return {"support": 1, "mixed": 0, "oppose": -1}[vote]


def build_cross_examination(analyses: list[InvestorAnalysis]) -> list[CrossExamination]:
    supporters = [analysis for analysis in analyses if analysis.preliminary_vote == "support"]
    opposers = [analysis for analysis in analyses if analysis.preliminary_vote == "oppose"]
    if not supporters or not opposers:
        return []
    challenger = opposers[0]
    respondent = supporters[0]
    return [
        CrossExamination(
            challenger=challenger.investor_name,
            respondent=respondent.investor_name,
            challenge=f"{challenger.investor_name} challenges whether the upside thesis underestimates downside and valuation compression risk.",
            response=f"{respondent.investor_name} responds that the quality of the asset and the identified drivers still justify measured conviction.",
        )
    ]


def build_proposals(packet: DueDiligencePacket, analyses: list[InvestorAnalysis]) -> list[Proposal]:
    avg_vote = mean(_vote_value(analysis.preliminary_vote) for analysis in analyses)
    proposals: list[Proposal] = []
    company_name = packet.classification.company_name or "the idea"
    if packet.stock_report:
        primary_risks = list(packet.stock_report.open_unknowns[:2])
        if not primary_risks and packet.technical_report:
            primary_risks = list(packet.technical_report.open_unknowns[:2])
        if not primary_risks:
            primary_risks = ["Execution risk", "Valuation risk"]
        primary_title = f"Watchlist {company_name}"
        primary_action = "Monitor and prepare for action"
        if avg_vote >= 0.35:
            primary_title = f"Accumulate {company_name}"
            primary_action = "Build or add to a position"
        elif avg_vote <= -0.35:
            primary_title = f"Avoid adding {company_name} for now"
            primary_action = "Stay on the sidelines"
        proposals.append(
            Proposal(
                proposal_id="P1",
                title=primary_title,
                action=primary_action,
                thesis=packet.stock_report.cheap_or_expensive if packet.stock_report else "The idea needs evidence-weighted conviction.",
                horizon="12-36 months",
                key_drivers=[
                    packet.stock_report.business_summary if packet.stock_report else "Business quality",
                    packet.technical_report.summary if packet.technical_report else "Diligence signals",
                ][:2],
                key_risks=primary_risks,
                portfolio_note="Size it modestly first and let follow-up data earn any increase in conviction.",
            )
        )
        proposals.append(
            Proposal(
                proposal_id="P2",
                title=f"Use staged entries for {company_name}",
                action="Start small and add only on better evidence or price",
                thesis="This keeps optionality while respecting valuation, macro, and information-risk uncertainty.",
                horizon="Next 2-4 quarters",
                key_drivers=["Additional diligence", "Improved valuation or confirming execution"],
                key_risks=["Opportunity cost", "Catching a deteriorating setup too early"],
                portfolio_note="Suitable for mixed-conviction investors who want exposure without full-size risk.",
            )
        )
        if packet.economic_report:
            proposals.append(
                Proposal(
                    proposal_id="P3",
                    title="Pair the idea with a macro-aware risk budget",
                    action="Cap exposure and hedge regime risk elsewhere in the portfolio",
                    thesis=f"Macro conditions matter because {packet.economic_report.summary.lower()}",
                    horizon="Current regime",
                    key_drivers=["Macro volatility", "Cross-market relative value"],
                    key_risks=["Over-hedging", "Missing upside if conditions ease quickly"],
                    portfolio_note="Useful when the idea is attractive but the regime is not fully supportive.",
                )
            )
        return proposals[:3]

    if packet.economic_report:
        proposals.append(
            Proposal(
                proposal_id="P1",
                title=f"Prefer the cheaper market: {packet.economic_report.cheapest_market}",
                action="Tilt new risk toward the cheapest major market",
                thesis=f"{packet.economic_report.cheapest_market} screens cheapest while {packet.economic_report.richest_market} screens richest on the selected valuation mix.",
                horizon="6-18 months",
                key_drivers=["Relative valuation", "Mean reversion", "Macro resilience"],
                key_risks=["Value traps", "Policy or currency shocks"],
                portfolio_note="Implement as a relative-value tilt rather than an all-or-nothing macro bet.",
            )
        )
        proposals.append(
            Proposal(
                proposal_id="P2",
                title="Keep a quality-and-liquidity bar for new risk",
                action="Require stronger balance sheets and funding resilience",
                thesis="The regime still demands selectivity even if broad markets remain constructive.",
                horizon="Current regime",
                key_drivers=["Credit conditions", "Labor and growth trend"],
                key_risks=["Lagging in momentum-led markets"],
                portfolio_note="This is the default position-sizing discipline across the panel.",
            )
        )
        proposals.append(
            Proposal(
                proposal_id="P3",
                title=f"Trim exposure to the richest market: {packet.economic_report.richest_market}",
                action="Avoid stretching for valuation-insensitive exposure",
                thesis="Expensive markets leave less room for error if macro or earnings expectations disappoint.",
                horizon="Next 2-4 quarters",
                key_drivers=["Valuation dispersion", "Earnings revisions"],
                key_risks=["Rich markets can stay rich longer than expected"],
                portfolio_note="Use trims and rebalancing, not forced liquidation.",
            )
        )
    return proposals[:3]


def build_votes(analyses: list[InvestorAnalysis], proposals: list[Proposal]) -> list[VoteRecord]:
    votes: list[VoteRecord] = []
    for proposal in proposals:
        title = proposal.title.lower()
        for analysis in analyses:
            stance = analysis.preliminary_vote
            if "avoid" in title or "trim" in title:
                vote = "support" if stance == "oppose" else "mixed" if stance == "mixed" else "oppose"
            elif "staged" in title or "watchlist" in title or "risk budget" in title or "quality-and-liquidity" in title:
                vote = "support" if stance != "support" else "mixed"
            else:
                vote = stance
            rationale = f"{analysis.investor_name} votes {vote} because {analysis.conclusion.lower()}"
            votes.append(
                VoteRecord(
                    proposal_id=proposal.proposal_id,
                    investor_name=analysis.investor_name,
                    vote=vote,
                    rationale=rationale,
                )
            )
    return votes


def run_investor_debate(
    knowledge_base: KnowledgeBase,
    investors: list[InvestorProfile],
    packet: DueDiligencePacket,
    company: CompanyRecord | None,
    market_data_client: MarketDataClient,
    macro_data_client: MacroDataClient,
    event_sink: RunEventSink | None = None,
) -> tuple[list[InvestorAnalysis], list[CrossExamination], list[Proposal], list[VoteRecord], int]:
    analyses = [build_investor_analysis(profile, packet) for profile in investors]
    profiles_by_slug = {profile.slug: profile for profile in investors}
    rounds_used = 0

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

        for analysis in analyses:
            analysis.follow_up_requests = _build_follow_up_requests(
                profiles_by_slug[analysis.investor_slug],
                packet,
            )

    cross_examinations = build_cross_examination(analyses)
    if event_sink:
        for exchange in cross_examinations:
            event_sink.record_dataclass(
                stage="cross_examination",
                event_type="exchange",
                title=f"{exchange.challenger} challenged {exchange.respondent}",
                payload=exchange,
                actor=exchange.challenger,
            )
    proposals = build_proposals(packet, analyses)
    if event_sink:
        for proposal in proposals:
            event_sink.record_dataclass(
                stage="proposal_synthesis",
                event_type="proposal",
                title=f"Moderator proposed {proposal.title}",
                payload=proposal,
                actor="moderator",
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
    return analyses, cross_examinations, proposals, votes, rounds_used
