from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ValidationError(ValueError):
    """Raised when data files fail validation."""


@dataclass(slots=True)
class CommentarySnapshot:
    as_of: str
    summary: str
    source_note: str


@dataclass(slots=True)
class HoldingsSnapshot:
    as_of: str
    note: str
    holdings: list[str]


@dataclass(slots=True)
class InvestorProfile:
    name: str
    slug: str
    style_tags: list[str]
    philosophy: str
    preferred_metrics: list[str]
    heuristics: list[str]
    risk_rules: list[str]
    portfolio_habits: list[str]
    commentary_snapshots: list[CommentarySnapshot]
    holdings_snapshots: list[HoldingsSnapshot]
    blind_spots: list[str]
    debate_role: str


@dataclass(slots=True)
class CompanyRecord:
    ticker: str
    name: str
    aliases: list[str]
    is_public: bool
    is_tech: bool
    sector: str
    industry: str
    archetype: str
    description: str
    technology: dict[str, Any]
    stock: dict[str, Any]


@dataclass(slots=True)
class MacroRecord:
    as_of: str
    scope: str
    metrics: dict[str, Any]
    supplemental_metrics: dict[str, Any]
    markets: dict[str, dict[str, Any]]


@dataclass(slots=True)
class QuestionClassification:
    category: str
    needs_technology_report: bool
    needs_stock_report: bool
    needs_macro_report: bool
    company_ticker: str | None
    company_name: str | None
    reason: str


@dataclass(slots=True)
class MetricSelection:
    scope: str
    lens: str
    chosen_metrics: list[str]
    excluded_metrics: list[str]
    rationale: str
    confidence: float


@dataclass(slots=True)
class TechnicalDueDiligenceReport:
    subject: str
    selected_dimensions: list[str]
    summary: str
    what_it_is: str
    world_impact: str
    feasibility: str
    requirements: list[str]
    constraints: list[str]
    competitive_landscape: list[str]
    preferred_technology: str
    preferred_rationale: str
    open_unknowns: list[str]


@dataclass(slots=True)
class StockDueDiligenceReport:
    company_name: str
    ticker: str
    as_of: str
    selected_metrics: list[str]
    excluded_metrics: list[str]
    price: float | None
    market_cap: float | None
    business_summary: str
    segment_mix: dict[str, float]
    operating_metrics: dict[str, Any]
    valuation_metrics: dict[str, Any]
    balance_sheet_metrics: dict[str, Any]
    cheap_or_expensive: str
    missing_metrics: list[str]
    open_unknowns: list[str]


@dataclass(slots=True)
class EconomicOverviewReport:
    as_of: str
    scope: str
    lens: str
    selected_metrics: list[str]
    excluded_metrics: list[str]
    core_metrics: dict[str, Any]
    market_comparison: list[dict[str, Any]]
    richest_market: str
    cheapest_market: str
    summary: str
    open_unknowns: list[str]


@dataclass(slots=True)
class InfoRequest:
    requestor: str
    team: str
    needed_metrics: list[str]
    reason: str


@dataclass(slots=True)
class InvestorAnalysis:
    investor_name: str
    investor_slug: str
    situation: str
    interpretation: str
    thesis: str
    falsification: str
    portfolio: str
    conclusion: str
    preliminary_vote: str
    follow_up_requests: list[InfoRequest] = field(default_factory=list)
    updates: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CrossExamination:
    challenger: str
    respondent: str
    challenge: str
    response: str


@dataclass(slots=True)
class Proposal:
    proposal_id: str
    title: str
    action: str
    thesis: str
    horizon: str
    key_drivers: list[str]
    key_risks: list[str]
    portfolio_note: str


@dataclass(slots=True)
class VoteRecord:
    proposal_id: str
    investor_name: str
    vote: str
    rationale: str


@dataclass(slots=True)
class ReportEvent:
    sequence: int
    stage: str
    event_type: str
    title: str
    actor: str | None
    payload: dict[str, Any]
    created_at: str


@dataclass(slots=True)
class SelfReviewRecommendation:
    category: str
    priority: str
    recommendation: str
    rationale: str


@dataclass(slots=True)
class SelfReview:
    review_id: str
    run_id: str
    summary: str
    recommendations: list[SelfReviewRecommendation]
    created_at: str


@dataclass(slots=True)
class DueDiligencePacket:
    classification: QuestionClassification
    metric_selections: list[MetricSelection]
    technical_report: TechnicalDueDiligenceReport | None
    stock_report: StockDueDiligenceReport | None
    economic_report: EconomicOverviewReport | None
    supplemental_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunResult:
    question: str
    context: str
    classification: QuestionClassification
    diligence_packet: DueDiligencePacket
    analyses: list[InvestorAnalysis]
    cross_examinations: list[CrossExamination]
    proposals: list[Proposal]
    votes: list[VoteRecord]
    follow_up_rounds_used: int
    run_id: str | None = None
    prompt_snapshot: dict[str, str] = field(default_factory=dict)
    transcript: list[ReportEvent] = field(default_factory=list)
    saved_markdown_path: str | None = None
    saved_json_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
