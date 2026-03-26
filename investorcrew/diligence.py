from __future__ import annotations

from typing import Any

from investorcrew.data_store import KnowledgeBase
from investorcrew.models import (
    CompanyRecord,
    EconomicOverviewReport,
    MetricSelection,
    StockDueDiligenceReport,
    TechnicalDueDiligenceReport,
)
from investorcrew.providers import LLMClient, MacroDataClient, MarketDataClient


def _valuation_bucket(company: CompanyRecord) -> str:
    valuation = company.stock.get("valuation_metrics", {})
    archetype = company.archetype
    if archetype == "semiconductor_hardware":
        forward_pe = valuation.get("forward_pe")
        ev_sales = valuation.get("ev_to_sales")
        if forward_pe is not None and forward_pe >= 30:
            return "expensive"
        if ev_sales is not None and ev_sales >= 15:
            return "expensive"
        if forward_pe is not None and forward_pe <= 18:
            return "cheap"
        return "fair"
    if archetype == "bank":
        ptbv = valuation.get("price_to_tangible_book")
        if ptbv is not None and ptbv >= 2.2:
            return "expensive"
        if ptbv is not None and ptbv <= 1.2:
            return "cheap"
        return "fair"
    if archetype == "energy_materials":
        fcf_yield = valuation.get("free_cash_flow_yield_pct")
        if fcf_yield is not None and fcf_yield >= 8:
            return "cheap"
        if fcf_yield is not None and fcf_yield <= 4:
            return "expensive"
        return "fair"
    if archetype == "developmental_energy_technology":
        price_to_book = valuation.get("price_to_book")
        if price_to_book is not None and price_to_book >= 8:
            return "speculative"
        if price_to_book is not None and price_to_book <= 3:
            return "early but less extended"
        return "pre-revenue"
    forward_pe = valuation.get("forward_pe")
    if forward_pe is not None and forward_pe >= 25:
        return "expensive"
    if forward_pe is not None and forward_pe <= 14:
        return "cheap"
    return "fair"


def _build_missing_metrics(knowledge_base: KnowledgeBase, company: CompanyRecord, metrics: list[str]) -> list[str]:
    missing = []
    for metric in metrics:
        if knowledge_base.metric_value_for_company(company, metric) is None:
            missing.append(metric)
    return missing


def build_technical_due_diligence(
    question: str,
    company: CompanyRecord | None,
    metric_selection: MetricSelection,
    llm_client: LLMClient,
) -> TechnicalDueDiligenceReport:
    subject = company.name if company else question.strip()
    technology = company.technology if company else {}
    summary = llm_client.summarize(
        f"Technical diligence for {subject}",
        [
            technology.get("summary", "Technology scope must be inferred from the prompt."),
            technology.get("world_impact", "Potential impact depends on adoption and real customer pain points."),
            technology.get("feasibility", "Feasibility remains uncertain without stronger engineering evidence."),
            technology.get("preferred_rationale", "The preferred approach should balance performance with deployment practicality."),
        ],
    )
    return TechnicalDueDiligenceReport(
        subject=subject,
        selected_dimensions=metric_selection.chosen_metrics,
        summary=summary,
        what_it_is=technology.get("summary", f"The question references {subject}, but the technology stack was not in the fixture set."),
        world_impact=technology.get("world_impact", "If execution succeeds, the technology could reshape a meaningful workflow or cost curve."),
        feasibility=technology.get("feasibility", "The build path is plausible but requires more proof on scale, talent, and economics."),
        requirements=list(technology.get("requirements", ["Domain expertise", "Capital", "Distribution"])),
        constraints=list(technology.get("constraints", ["Execution risk", "Adoption risk"])),
        competitive_landscape=list(technology.get("competitor_technologies", ["Competing approaches need to be mapped."])),
        preferred_technology=technology.get("preferred_technology", "No preferred technology selected yet"),
        preferred_rationale=technology.get("preferred_rationale", "There is not enough data to prefer one technical approach with high confidence."),
        open_unknowns=list(technology.get("open_unknowns", ["Unit economics at scale remain uncertain."])),
    )


def build_stock_due_diligence(
    company: CompanyRecord,
    metric_selection: MetricSelection,
    knowledge_base: KnowledgeBase,
    market_data_client: MarketDataClient,
) -> StockDueDiligenceReport:
    live_company = market_data_client.lookup_company(company.ticker) or company
    stock = live_company.stock
    missing_metrics = _build_missing_metrics(knowledge_base, live_company, metric_selection.chosen_metrics)
    valuation_bucket = _valuation_bucket(live_company)
    commentary = stock.get("commentary", "")
    return StockDueDiligenceReport(
        company_name=live_company.name,
        ticker=live_company.ticker,
        as_of=stock.get("as_of", "unknown"),
        selected_metrics=metric_selection.chosen_metrics,
        excluded_metrics=metric_selection.excluded_metrics,
        price=stock.get("price"),
        market_cap=stock.get("market_cap"),
        business_summary=live_company.description,
        segment_mix=dict(stock.get("segment_mix", {})),
        operating_metrics=dict(stock.get("operating_metrics", {})),
        valuation_metrics=dict(stock.get("valuation_metrics", {})),
        balance_sheet_metrics=dict(stock.get("balance_sheet_metrics", {})),
        cheap_or_expensive=f"{live_company.name} screens as {valuation_bucket}; {commentary}",
        missing_metrics=missing_metrics,
        open_unknowns=[f"Missing metric: {metric}" for metric in missing_metrics],
    )


def _market_richness_score(metrics: dict[str, Any]) -> float:
    score = 0.0
    weights = {
        "forward_pe": 1.2,
        "trailing_pe": 0.8,
        "cape": 0.7,
        "price_to_book": 0.6,
        "ev_to_ebitda": 0.8,
        "dividend_yield_pct": -1.0,
        "earnings_yield_minus_10y_pct": -1.3,
    }
    for metric, weight in weights.items():
        value = metrics.get(metric)
        if value is not None:
            score += float(value) * weight
    return score


def build_economic_overview(
    metric_selection: MetricSelection,
    macro_data_client: MacroDataClient,
    llm_client: LLMClient,
) -> EconomicOverviewReport:
    record = macro_data_client.get_overview()
    available_metrics = set(record.metrics)
    for market_metrics in record.markets.values():
        available_metrics.update(market_metrics)
    missing = [metric for metric in metric_selection.chosen_metrics if metric not in available_metrics]
    market_comparison: list[dict[str, Any]] = []
    for market_name, metrics in record.markets.items():
        market_comparison.append(
            {
                "market": market_name,
                "richness_score": round(_market_richness_score(metrics), 2),
                **metrics,
            }
        )
    market_comparison.sort(key=lambda item: float(item["richness_score"]), reverse=True)
    richest_market = market_comparison[0]["market"]
    cheapest_market = market_comparison[-1]["market"]
    summary = llm_client.summarize(
        "Economic overview",
        [
            f"US inflation is {record.metrics.get('cpi_yoy_pct', 'n/a')}% with unemployment at {record.metrics.get('unemployment_pct', 'n/a')}%.",
            f"Financial conditions show VIX at {record.metrics.get('vix', 'n/a')} and high-yield spreads at {record.metrics.get('high_yield_spread_bps', 'n/a')} bps.",
            f"{richest_market} screens richest while {cheapest_market} screens cheapest on the selected cross-market valuation mix.",
            record.metrics.get("sector_leadership", "Sector leadership remains mixed."),
        ],
    )
    return EconomicOverviewReport(
        as_of=record.as_of,
        scope=record.scope,
        lens=metric_selection.lens,
        selected_metrics=metric_selection.chosen_metrics,
        excluded_metrics=metric_selection.excluded_metrics,
        core_metrics={metric: record.metrics.get(metric) for metric in metric_selection.chosen_metrics if metric in record.metrics},
        market_comparison=market_comparison,
        richest_market=richest_market,
        cheapest_market=cheapest_market,
        summary=summary,
        open_unknowns=[f"Missing metric: {metric}" for metric in missing],
    )


def apply_stock_supplemental_metrics(
    knowledge_base: KnowledgeBase,
    company: CompanyRecord,
    report: StockDueDiligenceReport,
    market_data_client: MarketDataClient,
    requested_metrics: list[str],
) -> list[str]:
    updates = market_data_client.get_supplemental_metrics(company, requested_metrics)
    if updates:
        knowledge_base.merge_company_metrics(company, updates)
        report.operating_metrics.update({metric: value for metric, value in updates.items() if metric in report.selected_metrics})
        report.valuation_metrics.update({metric: value for metric, value in updates.items() if metric not in report.operating_metrics})
    remaining_missing = [metric for metric in report.missing_metrics if metric not in updates]
    report.missing_metrics = remaining_missing
    report.open_unknowns = [f"Missing metric: {metric}" for metric in remaining_missing]
    return list(updates.keys())


def apply_macro_supplemental_metrics(
    report: EconomicOverviewReport,
    macro_data_client: MacroDataClient,
    requested_metrics: list[str],
) -> list[str]:
    updates = macro_data_client.get_supplemental_metrics(requested_metrics)
    if updates:
        report.core_metrics.update(updates)
    remaining_missing = [metric for metric in report.open_unknowns if metric.replace("Missing metric: ", "") not in updates]
    report.open_unknowns = remaining_missing
    return list(updates.keys())
