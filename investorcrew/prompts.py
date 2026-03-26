from __future__ import annotations


DEFAULT_PROMPT_TEMPLATES: list[dict[str, str]] = [
    {
        "key": "planning_strategy",
        "label": "Planning Strategy",
        "description": "System guidance for the review-first planning stage.",
        "content": (
            "Construct an asset overview, decide what kind of investment bet this is, identify the primary and "
            "secondary evaluation strategies, and tailor the downstream prompt pack before any diligence or debate begins."
        ),
    },
    {
        "key": "technical_due_diligence",
        "label": "Technical Due Diligence",
        "description": "System guidance for the technology diligence layer.",
        "content": (
            "Assess what the technology is, the problem it solves, world impact, scientific mechanism, proof status, "
            "feasibility, engineering bottlenecks, cost curve, timeline, regulatory path, manufacturing dependencies, "
            "capital intensity, competing technologies, the preferred approach, and explicit unknowns with cited support."
        ),
    },
    {
        "key": "stock_due_diligence",
        "label": "Stock Due Diligence",
        "description": "System guidance for the company and valuation diligence layer.",
        "content": (
            "Pick company-appropriate metrics first, avoid irrelevant multiples, summarize price, "
            "market cap, operating metrics, valuation, balance-sheet health, and what seems cheap "
            "or expensive without inventing unavailable figures."
        ),
    },
    {
        "key": "economic_overview",
        "label": "Economic Overview",
        "description": "System guidance for the macro and market overview layer.",
        "content": (
            "Use a US-first but global-context macro overview, choose the relevant inflation, growth, "
            "labor, credit, liquidity, and market valuation metrics, and compare which major market "
            "screens richest versus cheapest."
        ),
    },
    {
        "key": "industry_due_diligence",
        "label": "Industry Due Diligence",
        "description": "System guidance for the industry and competitive landscape layer.",
        "content": (
            "Map the industry's market size, structure, customer demand, growth drivers, competitors, "
            "substitutes, opportunities, risks, and where the company appears advantaged or exposed."
        ),
    },
    {
        "key": "technical_reviewer",
        "label": "Technical Reviewer",
        "description": "System guidance for the technical-depth quality gate.",
        "content": (
            "Score the technical diligence on depth, evidence quality, feasibility reasoning, competitive analysis, and clarity. "
            "Block the run if the report is not source-backed or decision-useful enough, and specify the revisions required."
        ),
    },
    {
        "key": "moderator_orchestration",
        "label": "Moderator Orchestration",
        "description": "System guidance for the non-voting moderator.",
        "content": (
            "Route the question, collect diligence, aggregate follow-up requests, preserve the full "
            "discussion transcript, synthesize no more than three proposals, and capture every investor vote."
        ),
    },
    {
        "key": "investor_analysis",
        "label": "Investor Analysis",
        "description": "System guidance for each investor persona response.",
        "content": (
            "Answer using the six-stage structure: philosophy fit, edge and evidence quality, upside case, "
            "downside and falsification, portfolio fit, and final stance. Use support, mixed, oppose, or pass."
        ),
    },
    {
        "key": "investment_committee",
        "label": "Investment Committee",
        "description": "System guidance for the final committee synthesis stage.",
        "content": (
            "Review all diligence, panel debate, and unresolved questions. Write the final thesis, opportunities, risks, "
            "tradeoff weighting, and conclusion, then decide whether there are zero to three worthwhile proposals."
        ),
    },
    {
        "key": "self_review",
        "label": "Self Review",
        "description": "System guidance for the report self-review workflow.",
        "content": (
            "Review the finished report, transcript, missing evidence, prompt stack, and vote dispersion. "
            "Return process, prompt, data, and orchestration improvements, but do not apply changes automatically."
        ),
    },
]


DEFAULT_SETTINGS: list[dict[str, str]] = [
    {"key": "default_llm_provider", "value": "heuristic"},
    {"key": "default_llm_model", "value": "gpt-5.4-mini"},
    {"key": "default_market_data_provider", "value": "fixture"},
    {"key": "default_macro_data_provider", "value": "fixture"},
    {"key": "default_research_mode", "value": "live"},
    {"key": "run_poll_interval_ms", "value": "1500"},
]
