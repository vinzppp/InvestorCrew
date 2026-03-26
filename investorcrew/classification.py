from __future__ import annotations

from investorcrew.models import CompanyRecord, QuestionClassification


TECH_KEYWORDS = {
    "technology",
    "tech",
    "software",
    "hardware",
    "semiconductor",
    "chip",
    "cloud",
    "ai",
    "artificial intelligence",
    "platform",
    "robotics",
    "infrastructure",
}

STOCK_KEYWORDS = {
    "stock",
    "shares",
    "valuation",
    "financial statement",
    "earnings",
    "market cap",
    "buy",
    "sell",
    "invest",
    "own",
    "portfolio",
}

MACRO_KEYWORDS = {
    "economy",
    "economic",
    "macro",
    "markets",
    "market",
    "inflation",
    "fed",
    "rates",
    "recession",
    "gdp",
    "payrolls",
    "unemployment",
    "yield",
    "credit",
    "liquidity",
    "cpi",
    "pmi",
}


def classify_question(question: str, context: str, company: CompanyRecord | None) -> QuestionClassification:
    text = f"{question} {context}".lower()
    has_stock_language = any(keyword in text for keyword in STOCK_KEYWORDS)
    has_macro_language = any(keyword in text for keyword in MACRO_KEYWORDS)
    has_tech_language = any(keyword in text for keyword in TECH_KEYWORDS)

    if company and company.is_public and company.is_tech and (has_stock_language or has_tech_language):
        needs_macro_report = has_macro_language
        category = "mixed" if needs_macro_report or has_stock_language else "technology"
        return QuestionClassification(
            category=category,
            needs_technology_report=True,
            needs_stock_report=True if has_stock_language or company.is_public else False,
            needs_macro_report=needs_macro_report,
            company_ticker=company.ticker,
            company_name=company.name,
            reason=f"{company.name} is a public technology company, so both technical and stock diligence are relevant.",
        )

    if company and company.is_public and (has_stock_language or not has_tech_language):
        needs_macro_report = has_macro_language
        return QuestionClassification(
            category="mixed" if needs_macro_report else "stock",
            needs_technology_report=False,
            needs_stock_report=True,
            needs_macro_report=needs_macro_report,
            company_ticker=company.ticker,
            company_name=company.name,
            reason=f"{company.name} maps cleanly to a public company equity workflow.",
        )

    if has_macro_language and (has_stock_language or has_tech_language):
        return QuestionClassification(
            category="mixed",
            needs_technology_report=has_tech_language,
            needs_stock_report=has_stock_language,
            needs_macro_report=True,
            company_ticker=company.ticker if company else None,
            company_name=company.name if company else None,
            reason="The prompt mixes company or technology analysis with macro and market context.",
        )

    if has_macro_language:
        return QuestionClassification(
            category="macro",
            needs_technology_report=False,
            needs_stock_report=False,
            needs_macro_report=True,
            company_ticker=None,
            company_name=None,
            reason="The prompt is primarily about economic or market conditions.",
        )

    if has_tech_language:
        return QuestionClassification(
            category="technology",
            needs_technology_report=True,
            needs_stock_report=False,
            needs_macro_report=False,
            company_ticker=company.ticker if company else None,
            company_name=company.name if company else None,
            reason="The prompt is centered on a technology or technical feasibility question.",
        )

    return QuestionClassification(
        category="stock" if (company or has_stock_language) else "technology",
        needs_technology_report=False,
        needs_stock_report=bool(company) or has_stock_language,
        needs_macro_report=False,
        company_ticker=company.ticker if company else None,
        company_name=company.name if company else None,
        reason="Defaulted to the closest actionable analysis path based on the available signals.",
    )
