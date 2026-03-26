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
    lines.append("## Routing")
    lines.append(f"- Category: `{result.classification.category}`")
    lines.append(f"- Reason: {result.classification.reason}")
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
        lines.append(f"- Feasibility: {report.feasibility}")
        lines.append(f"- Preferred technology: {report.preferred_technology}")
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

    if result.diligence_packet.economic_report:
        report = result.diligence_packet.economic_report
        lines.append("## Economic Overview")
        lines.append(f"- Summary: {report.summary}")
        lines.append(f"- Richest market: {report.richest_market}")
        lines.append(f"- Cheapest market: {report.cheapest_market}")
        lines.append("")

    lines.append("## Investor Panel")
    for analysis in result.analyses:
        lines.append(f"### {analysis.investor_name}")
        lines.append(f"- Situation: {analysis.situation}")
        lines.append(f"- Interpretation: {analysis.interpretation}")
        lines.append(f"- Thesis: {analysis.thesis}")
        lines.append(f"- Falsification: {analysis.falsification}")
        lines.append(f"- Portfolio: {analysis.portfolio}")
        lines.append(f"- Conclusion: {analysis.conclusion}")
        for update in analysis.updates:
            lines.append(f"- Update: {update}")
        lines.append("")

    if result.cross_examinations:
        lines.append("## Cross Examination")
        for exchange in result.cross_examinations:
            lines.append(f"- {exchange.challenger} -> {exchange.respondent}: {exchange.challenge}")
            lines.append(f"- Response: {exchange.response}")
        lines.append("")

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

    lines.append("## Vote Table")
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

    if result.diligence_packet.supplemental_notes:
        lines.append("")
        lines.append("## Follow-Up Notes")
        for note in result.diligence_packet.supplemental_notes:
            lines.append(f"- {note}")

    return "\n".join(lines).strip() + "\n"


def render_json(result: RunResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
