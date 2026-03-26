from __future__ import annotations

import uuid
from datetime import UTC, datetime

from investorcrew.models import CompanyRecord, PlanningDraft, PlanningSource, QuestionClassification


CORE_SOURCE_BUCKETS = [
    "sec_filings",
    "investor_relations",
    "company_website",
    "transcripts",
    "industry_research",
]


STRATEGY_QUESTIONS: dict[str, list[str]] = {
    "tech_feasibility": [
        "What scientific or engineering mechanism has to work for the thesis to hold?",
        "What proof already exists, and what still remains unproven at production scale?",
        "Which bottlenecks or failure modes would break commercialization timelines?",
    ],
    "runway_and_financing": [
        "How much cash runway exists relative to the milestones still required?",
        "Which capital raises, project financing, or dilution paths could be needed before revenue scales?",
    ],
    "market_winner": [
        "Why should this business or technology win share versus the strongest alternatives?",
        "What adoption flywheel or ecosystem advantage makes the upside durable rather than cyclical?",
    ],
    "cash_flow_compounder": [
        "What proves the business converts growth into durable free cash flow?",
        "Which metrics best show resilience, pricing power, and reinvestment quality?",
    ],
    "valuation_mispricing": [
        "Which valuation lens is actually appropriate for this asset type?",
        "How much of the upside already appears priced in, and where is the margin of safety?",
    ],
    "macro_regime": [
        "Which macro regime matters most to this question right now?",
        "Which market or asset class looks richest versus cheapest on the chosen lens?",
    ],
    "inflation_resilience": [
        "Can the business or market maintain margins and demand through inflation or rate volatility?",
        "What operating or portfolio traits make it defensive versus rate-sensitive?",
    ],
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def determine_strategy(
    question: str,
    context: str,
    classification: QuestionClassification,
    company: CompanyRecord | None,
) -> tuple[str, list[str], str]:
    text = f"{question} {context}".lower()
    strategies: list[str] = []

    if company and company.archetype == "developmental_energy_technology":
        strategies = ["tech_feasibility", "runway_and_financing", "market_winner"]
    elif classification.category == "macro":
        strategies = ["macro_regime", "inflation_resilience"] if any(
            term in text for term in ("inflation", "rates", "fed", "yield", "pricing power")
        ) else ["macro_regime"]
    elif classification.needs_technology_report and classification.needs_stock_report:
        if company and company.archetype in {"software_platform", "semiconductor_hardware"}:
            strategies = ["market_winner", "valuation_mispricing", "cash_flow_compounder"]
        else:
            strategies = ["tech_feasibility", "runway_and_financing", "market_winner"]
    elif classification.needs_stock_report:
        strategies = ["cash_flow_compounder", "valuation_mispricing"]
        if any(term in text for term in ("inflation", "defensive", "pricing power")):
            strategies.append("inflation_resilience")
    elif classification.needs_technology_report:
        strategies = ["tech_feasibility", "market_winner"]

    if any(term in text for term in ("cheap", "expensive", "valuation", "multiple", "mispriced")):
        if "valuation_mispricing" not in strategies:
            strategies.append("valuation_mispricing")
    if any(term in text for term in ("cash flow", "free cash flow", "compounder", "quality")):
        if "cash_flow_compounder" not in strategies:
            strategies.append("cash_flow_compounder")

    if not strategies:
        strategies = ["valuation_mispricing"] if classification.needs_stock_report else ["macro_regime"]

    primary = strategies[0]
    secondary = strategies[1:3]

    if primary == "tech_feasibility" and company:
        rationale = (
            f"{company.name} is being treated as a technology-first investment where scientific feasibility, "
            "deployment milestones, capital needs, and regulatory execution matter more than mature valuation shortcuts."
        )
    elif primary == "cash_flow_compounder" and company:
        rationale = (
            f"{company.name} looks more like a business-quality and cash-generation decision than a frontier-technology bet."
        )
    elif primary == "macro_regime":
        rationale = "This question is primarily about the market and macro backdrop, so regime analysis should anchor the workflow."
    else:
        rationale = "The question needs a blended view of competitive positioning, economics, and risk before debating action."

    return primary, secondary, rationale


def build_asset_overview(question: str, classification: QuestionClassification, company: CompanyRecord | None) -> str:
    if company:
        return (
            f"{company.name} ({company.ticker}) is a {company.industry.lower()} company classified as {classification.category}. "
            f"The decision is whether {company.description.lower()}"
        )
    if classification.category == "macro":
        return (
            "This is a macro-first question focused on economic regime, market conditions, and cross-market valuation rather than a single company."
        )
    return f"The asset or idea in question is: {question.strip()}"


def build_key_study_questions(primary: str, secondary: list[str]) -> list[str]:
    questions: list[str] = []
    for strategy in [primary, *secondary]:
        for question in STRATEGY_QUESTIONS.get(strategy, []):
            if question not in questions:
                questions.append(question)
    return questions[:8]


def _summarize_products(company: CompanyRecord | None) -> str:
    if company is None:
        return "No single-company product map applies to this question."
    return company.technology.get("summary") or company.description


def _summarize_customers(company: CompanyRecord | None) -> str:
    if company is None:
        return "Customer demand should be inferred from the assets or markets named in the question."
    segment_mix = company.stock.get("segment_mix", {})
    if segment_mix:
        segments = ", ".join(f"{name} ({round(weight * 100)}%)" for name, weight in segment_mix.items())
        return f"Current business mix points to the following customer or demand centers: {segments}."
    return company.technology.get("world_impact") or "Customer overview is not richly captured in the local fixture set yet."


def _summarize_strategy(company: CompanyRecord | None, primary_strategy: str) -> str:
    if company is None:
        return f"The strategy should be evaluated primarily through {primary_strategy.replace('_', ' ')}."
    return (
        f"{company.name} appears to be pursuing a {primary_strategy.replace('_', ' ')} setup. "
        f"Management should be tested on how the company converts {company.description.lower()} into a durable advantage."
    )


def _summarize_leadership(company: CompanyRecord | None) -> str:
    if company is None:
        return "Leadership diligence is not applicable for a macro-only question."
    return (
        "Leadership should be reviewed through proxy filings, executive interviews, and investor presentations to "
        "test technical credibility, capital-allocation discipline, and how honestly management frames risk."
    )


def _summarize_shareholders(company: CompanyRecord | None) -> str:
    if company is None:
        return "Shareholder diligence is not applicable for a macro-only question."
    return (
        "Shareholder structure should be studied through governance filings, major holder disclosures, and financing history "
        "to understand alignment, dilution risk, and who can influence strategy."
    )


def _summarize_industry(company: CompanyRecord | None, classification: QuestionClassification) -> str:
    if company is None:
        if classification.category == "macro":
            return "Industry mapping is replaced here by regime, sector leadership, credit, and cross-market valuation analysis."
        return "Industry context must be inferred from the question."
    return (
        f"{company.name} operates in {company.industry.lower()}, so planning should cover market size, industry structure, "
        "demand drivers, substitutes, customer adoption friction, and regulatory or capital barriers."
    )


def _summarize_competition(company: CompanyRecord | None) -> str:
    if company is None:
        return "Competitive landscape depends on the assets or markets named in the question."
    competitors = company.technology.get("competitor_technologies", [])
    if competitors:
        return "Key competing approaches include " + ", ".join(str(item) for item in competitors[:5]) + "."
    return "Competitive landscape needs more explicit mapping across incumbents, substitutes, and adjacent technologies."


def _source_brief(sources: list[PlanningSource], buckets: list[str] | None = None) -> str:
    chosen = [
        source for source in sources if buckets is None or source.bucket in buckets
    ]
    if not chosen:
        return "No supporting sources are available yet. Be explicit about what remains unsupported."
    lines = []
    for source in chosen[:8]:
        published = f" ({source.published_at})" if source.published_at else ""
        url = f" [{source.url}]" if source.url else ""
        lines.append(f"- [{source.bucket or 'general'}] {source.publisher}: {source.title}{published}{url} :: {source.snippet}")
    return "\n".join(lines)


def _build_prompt(
    base_prompt: str,
    asset_overview: str,
    primary_strategy: str,
    secondary_strategies: list[str],
    key_study_questions: list[str],
    sources: list[PlanningSource],
    extra_directives: list[str],
) -> str:
    strategy_line = ", ".join([primary_strategy, *secondary_strategies]) if secondary_strategies else primary_strategy
    question_lines = "\n".join(f"- {question}" for question in key_study_questions)
    directive_lines = "\n".join(f"- {directive}" for directive in extra_directives)
    return (
        f"{base_prompt}\n\n"
        f"Asset overview:\n{asset_overview}\n\n"
        f"Primary evaluation strategy: {primary_strategy}\n"
        f"Secondary strategies: {', '.join(secondary_strategies) if secondary_strategies else 'None'}\n"
        f"Strategy stack: {strategy_line}\n\n"
        f"Key study questions:\n{question_lines}\n\n"
        f"Supporting sources:\n{_source_brief(sources)}\n\n"
        f"Additional directives:\n{directive_lines}"
    )


def _count_source_buckets(sources: list[PlanningSource]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        bucket = source.bucket or "general"
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _coverage_gaps(classification: QuestionClassification, sources: list[PlanningSource]) -> list[str]:
    if classification.category == "macro":
        return []
    buckets = {source.bucket for source in sources if source.source_kind == "core"}
    gaps = [bucket for bucket in CORE_SOURCE_BUCKETS if bucket not in buckets]
    if len([source for source in sources if source.source_kind == "core"]) < 15:
        gaps.append("source_depth")
    return gaps


def _listing_confirmation(company: CompanyRecord | None, sources: list[PlanningSource]) -> str:
    if company is None:
        return "No public listing confirmation was needed for this question."
    references = [source.publisher for source in sources if source.bucket == "listing_reference"]
    if references:
        unique = ", ".join(dict.fromkeys(references))
        return f"Listing status is treated as public and can be cross-checked through {unique}."
    if company.is_public:
        return f"{company.name} is treated as a public company, but listing-reference coverage is still thin."
    return f"{company.name} is not currently treated as a public company."


def _approval_warning(
    classification: QuestionClassification,
    source_count: int,
    coverage_gaps: list[str],
) -> str | None:
    warnings: list[str] = []
    if source_count < 15 and classification.category != "macro":
        warnings.append(
            f"Planning found {source_count} sources, below the 15-source target, so some diligence buckets may still be under-covered."
        )
    if coverage_gaps:
        rendered = ", ".join(item.replace("_", " ") for item in coverage_gaps)
        warnings.append(f"Coverage gaps remain in: {rendered}.")
    if classification.needs_technology_report and ("source_depth" in coverage_gaps or source_count == 0):
        warnings.append(
            "Technology-heavy diligence may still be blocked by the technical reviewer if the evidence trail stays thin."
        )
    return " ".join(warnings) if warnings else None


def build_planning_draft(
    question: str,
    context: str,
    classification: QuestionClassification,
    company: CompanyRecord | None,
    prompt_templates: dict[str, str],
    sources: list[PlanningSource],
    research_mode: str,
    plan_id: str | None = None,
) -> PlanningDraft:
    primary_strategy, secondary_strategies, rationale = determine_strategy(question, context, classification, company)
    asset_overview = build_asset_overview(question, classification, company)
    key_study_questions = build_key_study_questions(primary_strategy, secondary_strategies)
    source_buckets = _count_source_buckets(sources)
    coverage_gaps = _coverage_gaps(classification, sources)
    source_count = len(sources)

    prompt_pack = {
        "technical_due_diligence": _build_prompt(
            prompt_templates["technical_due_diligence"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Go deep on scientific mechanism, proof status, engineering bottlenecks, cost curve, timeline, regulatory path, and failure modes.",
                "Tie every important claim back to cited support or mark it unsupported.",
            ],
        ),
        "stock_due_diligence": _build_prompt(
            prompt_templates["stock_due_diligence"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Choose only company-appropriate metrics and explain why they matter for this investment style.",
                "For pre-commercial companies, emphasize runway, financing, milestone timing, and dilution risk before mature valuation shortcuts.",
            ],
        ),
        "economic_overview": _build_prompt(
            prompt_templates["economic_overview"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Focus only on the macro indicators that would change the investment decision.",
                "Call out which market or regime looks richer, cheaper, stronger, or more fragile and why.",
            ],
        ),
        "industry_due_diligence": _build_prompt(
            prompt_templates["industry_due_diligence"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Size the market, map competitors and substitutes, explain customer demand, and show the industry's best opportunities and structural risks.",
                "Connect industry structure back to whether the thesis is a market-winner bet, a financing bet, or a quality-and-cash-flow bet.",
            ],
        ),
        "technical_reviewer": _build_prompt(
            prompt_templates["technical_reviewer"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Reject shallow summaries, unsupported claims, and hand-wavy feasibility reasoning.",
                "Specify concrete revisions if the report is not yet strong enough to send to investors.",
            ],
        ),
        "investor_analysis": _build_prompt(
            prompt_templates["investor_analysis"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Investors should be willing to pass or oppose if the idea lacks fit, evidence, or margin of safety.",
                "Force the debate to engage directly with the key study questions rather than generic market commentary.",
            ],
        ),
        "investment_committee": _build_prompt(
            prompt_templates["investment_committee"],
            asset_overview,
            primary_strategy,
            secondary_strategies,
            key_study_questions,
            sources,
            [
                "Synthesize thesis, opportunities, risks, and tradeoffs without using numeric panel weighting.",
                "Return no more than three proposals and be comfortable with a no-invest conclusion if the evidence or philosophy fit is weak.",
            ],
        ),
    }

    return PlanningDraft(
        plan_id=plan_id or str(uuid.uuid4()),
        question=question,
        context=context,
        status="DRAFT",
        classification=classification,
        asset_overview=asset_overview,
        company_ticker=classification.company_ticker,
        company_name=classification.company_name,
        primary_strategy=primary_strategy,
        secondary_strategies=secondary_strategies,
        strategy_rationale=rationale,
        key_study_questions=key_study_questions,
        source_count=source_count,
        source_buckets=source_buckets,
        coverage_gaps=coverage_gaps,
        listing_confirmation=_listing_confirmation(company, sources),
        industry_summary=_summarize_industry(company, classification),
        leadership_summary=_summarize_leadership(company),
        shareholder_summary=_summarize_shareholders(company),
        strategy_summary=_summarize_strategy(company, primary_strategy),
        product_summary=_summarize_products(company),
        customer_summary=_summarize_customers(company),
        competitive_landscape_summary=_summarize_competition(company),
        prompt_pack=prompt_pack,
        sources=sources,
        research_mode=research_mode,
        approval_warning=_approval_warning(classification, source_count, coverage_gaps),
        approved_at=None,
        run_id=None,
    )


def approve_planning_draft(draft: PlanningDraft, run_id: str | None = None) -> PlanningDraft:
    return PlanningDraft(
        plan_id=draft.plan_id,
        question=draft.question,
        context=draft.context,
        status="APPROVED",
        classification=draft.classification,
        asset_overview=draft.asset_overview,
        company_ticker=draft.company_ticker,
        company_name=draft.company_name,
        primary_strategy=draft.primary_strategy,
        secondary_strategies=list(draft.secondary_strategies),
        strategy_rationale=draft.strategy_rationale,
        key_study_questions=list(draft.key_study_questions),
        source_count=draft.source_count,
        source_buckets=dict(draft.source_buckets),
        coverage_gaps=list(draft.coverage_gaps),
        listing_confirmation=draft.listing_confirmation,
        industry_summary=draft.industry_summary,
        leadership_summary=draft.leadership_summary,
        shareholder_summary=draft.shareholder_summary,
        strategy_summary=draft.strategy_summary,
        product_summary=draft.product_summary,
        customer_summary=draft.customer_summary,
        competitive_landscape_summary=draft.competitive_landscape_summary,
        prompt_pack=dict(draft.prompt_pack),
        sources=list(draft.sources),
        research_mode=draft.research_mode,
        approval_warning=draft.approval_warning,
        approved_at=_now(),
        run_id=run_id,
    )
