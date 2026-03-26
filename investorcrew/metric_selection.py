from __future__ import annotations

from investorcrew.models import CompanyRecord, MetricSelection


ARCHETYPE_POLICIES: dict[str, dict[str, list[str] | str | float]] = {
    "software_platform": {
        "lens": "asset-light tech/software",
        "chosen_metrics": [
            "ev_to_sales",
            "ev_to_gross_profit",
            "revenue_growth_pct",
            "gross_margin_pct",
            "free_cash_flow_margin_pct",
            "net_revenue_retention_pct",
        ],
        "excluded_metrics": ["price_to_book"],
        "rationale": "Asset-light software should be judged on growth quality, gross-profit economics, and cash conversion.",
        "confidence": 0.92,
    },
    "semiconductor_hardware": {
        "lens": "semiconductor and hardware cycle",
        "chosen_metrics": [
            "forward_pe",
            "ev_to_sales",
            "ev_to_gross_profit",
            "gross_margin_pct",
            "operating_margin_pct",
            "inventory_days",
            "capex_intensity_pct",
            "free_cash_flow_yield_pct",
        ],
        "excluded_metrics": ["price_to_book"],
        "rationale": "Semis need cycle-aware valuation plus margin, inventory, and capital intensity checks.",
        "confidence": 0.88,
    },
    "bank": {
        "lens": "bank balance-sheet valuation",
        "chosen_metrics": [
            "price_to_tangible_book",
            "roe_pct",
            "rotce_pct",
            "net_interest_margin_pct",
            "cet1_ratio_pct",
            "efficiency_ratio_pct",
        ],
        "excluded_metrics": ["ev_to_sales"],
        "rationale": "Banks should be framed through returns on capital, funding strength, and tangible equity valuation.",
        "confidence": 0.95,
    },
    "insurer": {
        "lens": "insurance underwriting and float quality",
        "chosen_metrics": [
            "price_to_book",
            "combined_ratio_pct",
            "roe_pct",
            "investment_yield_pct",
            "reserve_development_pct",
        ],
        "excluded_metrics": ["ev_to_sales"],
        "rationale": "Insurers are best judged on underwriting discipline, float economics, and book value growth.",
        "confidence": 0.9,
    },
    "industrial_cyclical": {
        "lens": "capital-intensive cyclical",
        "chosen_metrics": [
            "ev_to_ebitda",
            "normalized_free_cash_flow_billion",
            "net_debt_to_ebitda",
            "utilization_pct",
            "backlog_growth_pct",
            "operating_margin_pct",
        ],
        "excluded_metrics": ["price_to_book"],
        "rationale": "Cyclicals need normalized cash flow, leverage, and utilization rather than static multiples alone.",
        "confidence": 0.87,
    },
    "consumer_brand": {
        "lens": "consumer brand and unit economics",
        "chosen_metrics": [
            "forward_pe",
            "ev_to_ebitda",
            "organic_revenue_growth_pct",
            "gross_margin_pct",
            "free_cash_flow_yield_pct",
        ],
        "excluded_metrics": [],
        "rationale": "Consumer businesses need brand durability, pricing power, and cash generation checks.",
        "confidence": 0.85,
    },
    "energy_materials": {
        "lens": "commodity-linked capital cycle",
        "chosen_metrics": [
            "ev_to_ebitda",
            "free_cash_flow_yield_pct",
            "net_debt_to_capital_pct",
            "production_growth_pct",
            "break_even_oil_price_usd",
        ],
        "excluded_metrics": ["price_to_book"],
        "rationale": "Energy and materials should be judged on cycle-adjusted cash flow, leverage, and cost position.",
        "confidence": 0.86,
    },
    "developmental_energy_technology": {
        "lens": "pre-revenue energy technology",
        "chosen_metrics": [
            "cash_billion",
            "price_to_book",
            "levered_free_cash_flow_million",
            "return_on_equity_pct",
            "net_income_million",
            "first_revenue_expected_year",
            "first_commercial_reactor_target_year",
            "meta_power_campus_gw",
        ],
        "excluded_metrics": ["ev_to_ebitda", "forward_pe", "free_cash_flow_yield_pct"],
        "rationale": "Pre-revenue reactor developers should be judged on balance-sheet runway, milestone timing, and dilution risk rather than mature cash-flow multiples.",
        "confidence": 0.91,
    },
    "reit_asset_heavy": {
        "lens": "asset-heavy real estate",
        "chosen_metrics": [
            "price_to_ffo",
            "net_asset_value_discount_pct",
            "occupancy_pct",
            "net_debt_to_ebitda",
            "same_store_noi_growth_pct",
        ],
        "excluded_metrics": ["ev_to_sales"],
        "rationale": "REITs need cash-flow yields, asset coverage, and occupancy instead of sales multiples.",
        "confidence": 0.9,
    },
    "asset_manager": {
        "lens": "asset-management fee and flow durability",
        "chosen_metrics": [
            "forward_pe",
            "fee_rate_bps",
            "net_flows_billion",
            "operating_margin_pct",
            "return_on_equity_pct",
        ],
        "excluded_metrics": ["ev_to_sales"],
        "rationale": "Asset managers hinge on flows, margins, and earnings durability rather than raw asset size alone.",
        "confidence": 0.84,
    },
}

TECH_SELECTION = {
    "lens": "technical feasibility and competitive durability",
    "chosen_metrics": [
        "technology_readiness",
        "scaling_complexity",
        "capital_intensity",
        "talent_dependency",
        "deployment_friction",
        "competitive_intensity",
        "moat_durability",
    ],
    "excluded_metrics": [],
    "rationale": "Technical diligence should separate impact from buildability and competitive durability.",
    "confidence": 0.83,
}

MACRO_POLICIES: dict[str, list[str]] = {
    "inflation": ["cpi_yoy_pct", "core_cpi_yoy_pct", "policy_rate_pct", "breakeven_inflation_pct", "wage_growth_pct"],
    "growth": ["gdp_nowcast_pct", "ism_manufacturing", "ism_services", "retail_sales_yoy_pct", "earnings_revision_breadth_pct"],
    "labor": ["unemployment_pct", "nonfarm_payrolls_k", "job_openings_million", "initial_claims_k"],
    "credit_liquidity": ["10y_2y_spread_bps", "high_yield_spread_bps", "financial_conditions_index", "dxy"],
    "market_conditions": ["vix", "sp500_ytd_pct", "market_breadth_pct_above_200dma", "sector_leadership"],
    "cross_market_valuation": [
        "forward_pe",
        "trailing_pe",
        "cape",
        "price_to_book",
        "ev_to_ebitda",
        "dividend_yield_pct",
        "earnings_yield_minus_10y_pct",
    ],
}


def select_company_metrics(company: CompanyRecord) -> MetricSelection:
    policy = ARCHETYPE_POLICIES.get(company.archetype, ARCHETYPE_POLICIES["industrial_cyclical"])
    return MetricSelection(
        scope="company",
        lens=str(policy["lens"]),
        chosen_metrics=list(policy["chosen_metrics"]),
        excluded_metrics=list(policy["excluded_metrics"]),
        rationale=str(policy["rationale"]),
        confidence=float(policy["confidence"]),
    )


def select_technology_metrics() -> MetricSelection:
    return MetricSelection(
        scope="technology",
        lens=str(TECH_SELECTION["lens"]),
        chosen_metrics=list(TECH_SELECTION["chosen_metrics"]),
        excluded_metrics=list(TECH_SELECTION["excluded_metrics"]),
        rationale=str(TECH_SELECTION["rationale"]),
        confidence=float(TECH_SELECTION["confidence"]),
    )


def select_macro_metrics(question: str) -> MetricSelection:
    lowered = question.lower()
    selected_lenses: list[str] = []
    if any(term in lowered for term in ("inflation", "cpi", "rates", "fed")):
        selected_lenses.append("inflation")
    if any(term in lowered for term in ("growth", "gdp", "slowdown", "recession", "pmi", "ism")):
        selected_lenses.append("growth")
    if any(term in lowered for term in ("jobs", "labor", "employment", "payrolls", "unemployment")):
        selected_lenses.append("labor")
    if any(term in lowered for term in ("credit", "liquidity", "spread", "yield curve", "dollar")):
        selected_lenses.append("credit_liquidity")
    if any(term in lowered for term in ("market", "markets", "stocks", "valuation", "expensive", "cheap")):
        selected_lenses.append("market_conditions")
        selected_lenses.append("cross_market_valuation")
    if not selected_lenses:
        selected_lenses = ["growth", "market_conditions", "cross_market_valuation"]

    chosen_metrics: list[str] = []
    for lens in selected_lenses:
        for metric in MACRO_POLICIES[lens]:
            if metric not in chosen_metrics:
                chosen_metrics.append(metric)

    return MetricSelection(
        scope="macro",
        lens="+".join(selected_lenses),
        chosen_metrics=chosen_metrics,
        excluded_metrics=["price_to_book_as_primary_for_asset_light_indices"],
        rationale="Selected a macro dashboard that matches the prompt's regime questions and cross-market comparison needs.",
        confidence=0.89,
    )
