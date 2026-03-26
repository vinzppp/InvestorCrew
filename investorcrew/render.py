from __future__ import annotations

import json
from typing import Any

from investorcrew.models import RunResult


def _humanize_metric(metric: str) -> str:
    replacements = {
        "pct": "%",
        "ev": "EV",
        "pe": "P/E",
        "ebitda": "EBITDA",
        "gdp": "GDP",
        "cpi": "CPI",
        "pmi": "PMI",
        "ism": "ISM",
        "vix": "VIX",
        "roe": "ROE",
        "rotce": "ROTCE",
        "nim": "NIM",
        "ffo": "FFO",
    }
    words = metric.split("_")
    rendered = []
    for word in words:
        rendered.append(replacements.get(word, word.upper() if len(word) <= 3 else word.capitalize()))
    return " ".join(rendered)


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        return f"{value:.2f}"
    return str(value)


def render_markdown(result: RunResult) -> str:
    lines: list[str] = []
    lines.append("# InvestorCrew Memo")
    lines.append("")
    lines.append("## Question")
    lines.append(result.question)
    lines.append("")
    if result.planning_draft:
        lines.append("## Approved Evaluation Plan")
        lines.append(f"- Asset overview: {result.planning_draft.asset_overview}")
        lines.append(f"- Primary strategy: `{result.planning_draft.primary_strategy}`")
        if result.planning_draft.secondary_strategies:
            lines.append(f"- Secondary strategies: {', '.join(result.planning_draft.secondary_strategies)}")
        lines.append(f"- Strategy rationale: {result.planning_draft.strategy_rationale}")
        lines.append(f"- Listing confirmation: {result.planning_draft.listing_confirmation}")
        lines.append(f"- Source count: {result.planning_draft.source_count}")
        if result.planning_draft.source_buckets:
            lines.append(
                "- Source buckets: "
                + ", ".join(f"{bucket}={count}" for bucket, count in result.planning_draft.source_buckets.items())
            )
        if result.planning_draft.coverage_gaps:
            lines.append("- Coverage gaps: " + ", ".join(result.planning_draft.coverage_gaps))
        if result.planning_draft.key_study_questions:
            lines.append("- Key study questions:")
            for question in result.planning_draft.key_study_questions:
                lines.append(f"  - {question}")
        if result.planning_draft.sources:
            lines.append("- Planning sources:")
            for source in result.planning_draft.sources:
                published = f" ({source.published_at})" if source.published_at else ""
                url = f" [{source.url}]" if source.url else ""
                bucket = f"[{source.bucket}] " if source.bucket else ""
                lines.append(f"  - {bucket}{source.publisher}: {source.title}{published}{url}")
        if result.planning_draft.approval_warning:
            lines.append(f"- Warning: {result.planning_draft.approval_warning}")
        lines.append("")
    lines.append("## Metric Selection")
    for selection in result.diligence_packet.metric_selections:
        lines.append(f"- `{selection.scope}` via `{selection.lens}`: {', '.join(_humanize_metric(metric) for metric in selection.chosen_metrics)}")
        if selection.excluded_metrics:
            lines.append(f"  Excluded: {', '.join(_humanize_metric(metric) for metric in selection.excluded_metrics)}")
    lines.append("")

    if result.diligence_packet.technical_report:
        report = result.diligence_packet.technical_report
        lines.append("## Technical Due Diligence")
        lines.append(f"- Subject: {report.subject}")
        lines.append(f"- Summary: {report.summary}")
        lines.append(f"- Scientific mechanism: {report.scientific_mechanism}")
        lines.append(f"- Proof status: {report.proof_status}")
        lines.append(f"- Feasibility: {report.feasibility}")
        lines.append(f"- Timeline: {report.timeline}")
        lines.append(f"- Regulatory path: {report.regulatory_path}")
        lines.append(f"- Preferred technology: {report.preferred_technology}")
        if report.citations:
            lines.append("- Citations:")
            for source in report.citations:
                published = f" ({source.published_at})" if source.published_at else ""
                url = f" [{source.url}]" if source.url else ""
                lines.append(f"  - {source.publisher}: {source.title}{published}{url}")
        lines.append("")

    if result.technical_review_rounds:
        lines.append("## Technical Review")
        for review in result.technical_review_rounds:
            lines.append(f"- Round {review.round_index}: score {review.overall_score:.2f}, passes={review.passes}, blocked={review.blocked}")
            for finding in review.findings:
                lines.append(f"  - Finding: {finding}")
            for revision in review.required_revisions:
                lines.append(f"  - Revision: {revision}")
        lines.append("")

    if result.diligence_packet.stock_report:
        report = result.diligence_packet.stock_report
        lines.append("## Stock Due Diligence")
        lines.append(f"- Company: {report.company_name} ({report.ticker})")
        lines.append(f"- Price: {_format_value(report.price)}")
        lines.append(f"- Market cap: {_format_value(report.market_cap)}")
        lines.append(f"- Valuation read: {report.cheap_or_expensive}")
        if report.missing_metrics:
            lines.append(f"- Missing metrics: {', '.join(_humanize_metric(metric) for metric in report.missing_metrics)}")
        lines.append("")

    if result.diligence_packet.industry_report:
        report = result.diligence_packet.industry_report
        lines.append("## Industry Due Diligence")
        lines.append(f"- Subject: {report.subject}")
        lines.append(f"- Summary: {report.summary}")
        lines.append(f"- Market size: {report.market_size}")
        lines.append(f"- Market structure: {report.market_structure}")
        lines.append(f"- Growth drivers: {', '.join(report.growth_drivers)}")
        lines.append(f"- Competitors: {', '.join(report.competitors)}")
        lines.append(f"- Opportunities: {', '.join(report.opportunities)}")
        lines.append(f"- Risks: {', '.join(report.risks)}")
        lines.append("")

    if result.diligence_packet.economic_report:
        report = result.diligence_packet.economic_report
        lines.append("## Economic Overview")
        lines.append(f"- Summary: {report.summary}")
        lines.append(f"- Richest market: {report.richest_market}")
        lines.append(f"- Cheapest market: {report.cheapest_market}")
    lines.append("")

    if result.committee_memo:
        lines.append("## Investment Committee Conclusion")
        lines.append(f"- Thesis: {result.committee_memo.thesis}")
        lines.append(f"- Opportunities: {', '.join(result.committee_memo.opportunities)}")
        lines.append(f"- Risks: {', '.join(result.committee_memo.risks)}")
        lines.append(f"- Weighing: {result.committee_memo.weighing}")
        lines.append(f"- Conclusion: {result.committee_memo.conclusion}")
        lines.append("")

    lines.append("## Investor Panel")
    for analysis in result.analyses:
        lines.append(f"### {analysis.investor_name}")
        lines.append(f"- Philosophy fit: {analysis.situation}")
        lines.append(f"- Edge and evidence: {analysis.interpretation}")
        lines.append(f"- Upside case: {analysis.thesis}")
        lines.append(f"- Downside and falsification: {analysis.falsification}")
        lines.append(f"- Portfolio fit: {analysis.portfolio}")
        lines.append(f"- Final stance: {analysis.conclusion}")
        for update in analysis.updates:
            lines.append(f"- Update: {update}")
        lines.append("")

    if result.cross_examinations:
        lines.append("## Cross Examination")
        for exchange in result.cross_examinations:
            lines.append(f"- {exchange.challenger} -> {exchange.respondent}: {exchange.challenge}")
            lines.append(f"- Response: {exchange.response}")
            if exchange.committee_commentary:
                lines.append(f"- Committee note: {exchange.committee_commentary}")
        lines.append("")

    if result.discussion_log:
        lines.append("## Discussion Log")
        for entry in result.discussion_log:
            lines.append(f"- {entry.speaker} ({entry.role}, {entry.section}): {entry.content}")
        lines.append("")

    lines.append("## Final Disposition")
    lines.append(f"- {result.final_disposition}")
    if result.blocked_reason:
        lines.append(f"- Blocked reason: {result.blocked_reason}")
    lines.append("")

    if result.proposals:
        lines.append("## Proposals")
        for proposal in result.proposals:
            lines.append(f"### {proposal.proposal_id}: {proposal.title}")
            lines.append(f"- Action: {proposal.action}")
            lines.append(f"- Thesis: {proposal.thesis}")
            lines.append(f"- Horizon: {proposal.horizon}")
            lines.append(f"- Drivers: {', '.join(proposal.key_drivers)}")
            lines.append(f"- Risks: {', '.join(proposal.key_risks)}")
            lines.append(f"- Portfolio note: {proposal.portfolio_note}")
            lines.append("")
    else:
        lines.append("## Proposals")
        lines.append("- No proposal cleared the evidence and philosophy-fit bar for this run.")
        lines.append("")

    lines.append("## Vote Table")
    if result.proposals:
        header = "| Investor | " + " | ".join(proposal.proposal_id for proposal in result.proposals) + " |"
        divider = "|" + "---|" * (len(result.proposals) + 1)
        lines.append(header)
        lines.append(divider)
        investor_names = [analysis.investor_name for analysis in result.analyses]
        for investor_name in investor_names:
            row = [investor_name]
            for proposal in result.proposals:
                vote = next(
                    record.vote
                    for record in result.votes
                    if record.proposal_id == proposal.proposal_id and record.investor_name == investor_name
                )
                row.append(vote)
            lines.append("| " + " | ".join(row) + " |")
    else:
        lines.append("- No proposal vote table because the disposition was no-invest.")

    if result.diligence_packet.supplemental_notes:
        lines.append("")
        lines.append("## Follow-Up Notes")
        for note in result.diligence_packet.supplemental_notes:
            lines.append(f"- {note}")

    return "\n".join(lines).strip() + "\n"


def render_json(result: RunResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
