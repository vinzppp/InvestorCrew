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
class PlanningSource:
    title: str
    url: str
    publisher: str
    published_at: str | None
    snippet: str
    bucket: str = ""
    source_kind: str = "core"


@dataclass(slots=True)
class PlanningDraft:
    plan_id: str
    question: str
    context: str
    status: str
    classification: QuestionClassification
    asset_overview: str
    company_ticker: str | None
    company_name: str | None
    primary_strategy: str
    secondary_strategies: list[str]
    strategy_rationale: str
    key_study_questions: list[str]
    source_count: int
    source_buckets: dict[str, int]
    coverage_gaps: list[str]
    listing_confirmation: str
    industry_summary: str
    leadership_summary: str
    shareholder_summary: str
    strategy_summary: str
    product_summary: str
    customer_summary: str
    competitive_landscape_summary: str
    prompt_pack: dict[str, str]
    sources: list[PlanningSource]
    research_mode: str
    approval_warning: str | None = None
    approved_at: str | None = None
    run_id: str | None = None


@dataclass(slots=True)
class TechnicalDueDiligenceReport:
    subject: str
    selected_dimensions: list[str]
    summary: str
    what_it_is: str
    world_impact: str
    scientific_mechanism: str
    proof_status: str
    feasibility: str
    engineering_bottlenecks: list[str]
    requirements: list[str]
    constraints: list[str]
    competitive_landscape: list[str]
    preferred_technology: str
    preferred_rationale: str
    cost_curve: str
    timeline: str
    regulatory_path: str
    manufacturing_dependencies: list[str]
    capital_intensity: str
    failure_modes: list[str]
    citations: list[PlanningSource]
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
class IndustryDueDiligenceReport:
    subject: str
    summary: str
    market_size: str
    market_structure: str
    growth_drivers: list[str]
    competitors: list[str]
    opportunities: list[str]
    risks: list[str]
    customer_overview: str
    citations: list[PlanningSource]


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
    committee_commentary: str = ""


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
class TechnicalReviewRound:
    round_index: int
    passes: bool
    blocked: bool
    overall_score: float
    depth_score: float
    evidence_quality_score: float
    feasibility_reasoning_score: float
    competitive_analysis_score: float
    clarity_score: float
    summary: str
    findings: list[str]
    required_revisions: list[str]


@dataclass(slots=True)
class DiscussionEntry:
    speaker: str
    role: str
    section: str
    content: str


@dataclass(slots=True)
class CommitteeMemo:
    thesis: str
    opportunities: list[str]
    risks: list[str]
    weighing: str
    conclusion: str
    disposition: str


@dataclass(slots=True)
class DueDiligencePacket:
    classification: QuestionClassification
    metric_selections: list[MetricSelection]
    technical_report: TechnicalDueDiligenceReport | None
    stock_report: StockDueDiligenceReport | None
    economic_report: EconomicOverviewReport | None
    industry_report: IndustryDueDiligenceReport | None
    supplemental_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunResult:
    question: str
    context: str
    classification: QuestionClassification
    planning_draft: PlanningDraft | None
    diligence_packet: DueDiligencePacket
    technical_review_rounds: list[TechnicalReviewRound]
    analyses: list[InvestorAnalysis]
    cross_examinations: list[CrossExamination]
    committee_memo: CommitteeMemo | None
    committee_reasoning: list[str]
    discussion_log: list[DiscussionEntry]
    proposals: list[Proposal]
    votes: list[VoteRecord]
    follow_up_rounds_used: int
    final_disposition: str = "watchlist"
    blocked_reason: str | None = None
    run_id: str | None = None
    prompt_snapshot: dict[str, str] = field(default_factory=dict)
    transcript: list[ReportEvent] = field(default_factory=list)
    saved_markdown_path: str | None = None
    saved_json_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
