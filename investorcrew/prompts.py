from __future__ import annotations


DEFAULT_PROMPT_TEMPLATES: list[dict[str, str]] = [
    {
        "key": "technical_due_diligence",
        "label": "Technical Due Diligence",
        "description": "System guidance for the technology diligence layer.",
        "content": (
            "Assess what the technology is, the problem it solves, world impact, feasibility, "
            "infrastructure needs, adoption and regulatory constraints, competing technologies, "
            "and the preferred approach with explicit unknowns."
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
            "Answer using the six-stage structure: situation and key metrics, interpretation, thesis and upside, "
            "falsification and downside, portfolio fit, and final conclusion plus vote."
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
    {"key": "run_poll_interval_ms", "value": "1500"},
]
