from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from investorcrew.artifacts import build_report_output_dir, save_run_artifacts
from investorcrew.classification import classify_question
from investorcrew.config import AppConfig
from investorcrew.data_store import KnowledgeBase
from investorcrew.debate import run_investor_debate
from investorcrew.diligence import (
    build_economic_overview,
    build_industry_due_diligence,
    build_stock_due_diligence,
    build_technical_due_diligence,
)
from investorcrew.events import RunEventSink
from investorcrew.metric_selection import select_company_metrics, select_macro_metrics, select_technology_metrics
from investorcrew.models import (
    DueDiligencePacket,
    MetricSelection,
    PlanningDraft,
    RunResult,
    TechnicalReviewRound,
)
from investorcrew.planning import approve_planning_draft, build_planning_draft
from investorcrew.providers import (
    build_llm_client,
    build_macro_data_client,
    build_market_data_client,
    build_research_client,
)
from investorcrew.prompts import DEFAULT_PROMPT_TEMPLATES
from investorcrew.render import render_json, render_markdown
from investorcrew.review import build_self_review
from investorcrew.store import SqliteStore
from investorcrew.technical_review import review_technical_report, strengthen_technical_report


def _now() -> str:
    return datetime.now(UTC).isoformat()


class InvestorCrewService:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.seed_knowledge_base = KnowledgeBase(self.config.data_dir)
        self.store = SqliteStore(
            db_path=self.config.db_path,
            seed_data_dir=self.config.data_dir,
            outputs_dir=self.config.outputs_dir,
        )
        self.store.initialize()

    def _ensure_company(self, question: str, context: str) -> tuple[Any, Any | None, dict[str, Any] | None]:
        knowledge_base = self.store.load_runtime_knowledge_base()
        company = knowledge_base.find_company(f"{question}\n{context}")
        fixture_event = None
        if company is None:
            seed_company = self.seed_knowledge_base.ensure_company_fixture(question=question, context=context)
            if seed_company is not None:
                self.store.upsert_company_record(seed_company)
                knowledge_base = self.store.load_runtime_knowledge_base()
                company = knowledge_base.find_company(seed_company.ticker)
                fixture_event = {"ticker": seed_company.ticker, "name": seed_company.name}
        return knowledge_base, company, fixture_event

    def _planning_draft_from_row(self, raw: dict[str, Any]) -> PlanningDraft:
        return self.store._planning_draft_from_raw(raw["draft"])

    def _prompt_snapshot(self) -> dict[str, str]:
        snapshot = self.store.get_prompt_snapshot()
        for template in DEFAULT_PROMPT_TEMPLATES:
            snapshot.setdefault(template["key"], template["content"])
        return snapshot

    def generate_plan(
        self,
        question: str,
        context: str = "",
        research_mode: str | None = None,
    ) -> PlanningDraft:
        knowledge_base, company, _ = self._ensure_company(question, context)
        prompt_snapshot = self._prompt_snapshot()
        classification = classify_question(question, context, company)
        research_client = build_research_client(self.config, knowledge_base)
        requested_mode = research_mode or "live"
        actual_mode, sources = research_client.collect_sources(question=question, context=context, company=company, mode=requested_mode)
        draft = build_planning_draft(
            question=question,
            context=context,
            classification=classification,
            company=company,
            prompt_templates=prompt_snapshot,
            sources=sources,
            research_mode=actual_mode,
        )
        self.store.save_planning_draft(draft)
        return draft

    def create_plan(self, question: str, context: str = "", research_mode: str | None = None) -> dict[str, Any]:
        draft = self.generate_plan(question=question, context=context, research_mode=research_mode)
        return asdict(draft)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        row = self.store.get_planning_draft(plan_id)
        return row["draft"]

    def update_plan(self, plan_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        updated = self.store.update_planning_draft(plan_id, payload)
        return updated["draft"]

    def queue_run(self, question: str, context: str = "") -> tuple[str, PlanningDraft]:
        draft = self.generate_plan(question=question, context=context)
        run_id = self.store.create_run(question=question, context=context)
        approved = approve_planning_draft(draft, run_id=run_id)
        self.store.save_planning_draft(approved)
        self.store.link_plan_to_run(approved.plan_id, run_id, approved.approved_at or _now())
        return run_id, approved

    def approve_plan(self, plan_id: str) -> tuple[dict[str, Any], PlanningDraft]:
        current = self.store.get_planning_draft(plan_id)
        draft = self._planning_draft_from_row(current)
        run_id = draft.run_id or self.store.create_run(question=draft.question, context=draft.context)
        approved = approve_planning_draft(draft, run_id=run_id)
        self.store.save_planning_draft(approved)
        self.store.link_plan_to_run(plan_id, run_id, approved.approved_at or _now())
        return self.store.get_run(run_id), approved

    def ask(
        self,
        question: str,
        context: str = "",
        planning_draft: PlanningDraft | None = None,
        run_id: str | None = None,
        prompt_snapshot: dict[str, str] | None = None,
        event_sink: RunEventSink | None = None,
    ) -> RunResult:
        knowledge_base, company, fixture_event = self._ensure_company(question, context)

        llm_client = build_llm_client(self.config)
        market_data_client = build_market_data_client(self.config, knowledge_base)
        macro_data_client = build_macro_data_client(self.config, knowledge_base)
        classification = planning_draft.classification if planning_draft else classify_question(question, context, company)

        if planning_draft is None:
            research_client = build_research_client(self.config, knowledge_base)
            actual_mode, sources = research_client.collect_sources(question=question, context=context, company=company, mode="live")
            planning_draft = build_planning_draft(
                question=question,
                context=context,
                classification=classification,
                company=company,
                prompt_templates=prompt_snapshot or self._prompt_snapshot(),
                sources=sources,
                research_mode=actual_mode,
            )

        if fixture_event and event_sink:
            event_sink.record(
                stage="company_lookup",
                event_type="fixture_created",
                title=f"Created placeholder fixture for {fixture_event['ticker']}",
                payload=fixture_event,
                actor="system",
            )

        if event_sink:
            event_sink.record_dataclass(
                stage="planning",
                event_type="approved_draft",
                title="Approved planning draft loaded",
                payload=planning_draft,
                actor="planner",
            )
            event_sink.record(
                stage="classification",
                event_type="classification",
                title="Question classified",
                payload={
                    "category": classification.category,
                    "reason": classification.reason,
                    "company_ticker": classification.company_ticker,
                    "company_name": classification.company_name,
                },
                actor="moderator",
            )

        if run_id:
            self.store.mark_run_running(
                run_id=run_id,
                company_ticker=classification.company_ticker,
                company_name=classification.company_name,
            )

        metric_selections: list[MetricSelection] = []
        technical_report = None
        stock_report = None
        economic_report = None
        industry_report = None
        technical_review_rounds: list[TechnicalReviewRound] = []

        if classification.needs_technology_report:
            technology_selection = select_technology_metrics()
            metric_selections.append(technology_selection)
            if event_sink:
                event_sink.record_dataclass(
                    stage="metric_selection",
                    event_type="selection",
                    title="Selected technology diligence metrics",
                    payload=technology_selection,
                    actor="technical_diligence",
                )
            technical_report = build_technical_due_diligence(
                question=question,
                company=company,
                metric_selection=technology_selection,
                planning_draft=planning_draft,
                sources=planning_draft.sources,
                llm_client=llm_client,
            )
            for round_index in range(1, 4):
                review = review_technical_report(technical_report, planning_draft, round_index=round_index)
                technical_review_rounds.append(review)
                if event_sink:
                    event_sink.record_dataclass(
                        stage="technical_review",
                        event_type="review",
                        title=f"Technical review round {round_index}",
                        payload=review,
                        actor="technical_reviewer",
                    )
                if review.passes:
                    break
                if review.blocked:
                    break
                technical_report = strengthen_technical_report(technical_report, planning_draft, review)

            if event_sink:
                event_sink.record_dataclass(
                    stage="technical_diligence",
                    event_type="artifact",
                    title="Technical due diligence completed",
                    payload=technical_report,
                    actor="technical_diligence",
                )
            if run_id and technical_report:
                self.store.save_artifact(run_id, "technical_report", "Technical Due Diligence", asdict(technical_report))
                for review in technical_review_rounds:
                    self.store.save_artifact(
                        run_id,
                        "technical_review",
                        f"Technical Review Round {review.round_index}",
                        asdict(review),
                    )

        if classification.needs_stock_report and company:
            company_selection = select_company_metrics(company)
            metric_selections.append(company_selection)
            if event_sink:
                event_sink.record_dataclass(
                    stage="metric_selection",
                    event_type="selection",
                    title="Selected company diligence metrics",
                    payload=company_selection,
                    actor="stock_diligence",
                )
            stock_report = build_stock_due_diligence(
                company=company,
                metric_selection=company_selection,
                knowledge_base=knowledge_base,
                market_data_client=market_data_client,
            )
            if event_sink:
                event_sink.record_dataclass(
                    stage="stock_diligence",
                    event_type="artifact",
                    title="Stock due diligence completed",
                    payload=stock_report,
                    actor="stock_diligence",
                )
            if run_id:
                self.store.save_artifact(run_id, "stock_report", "Stock Due Diligence", asdict(stock_report))

        if company and classification.category in {"stock", "mixed", "technology"}:
            industry_report = build_industry_due_diligence(
                question=question,
                company=company,
                planning_draft=planning_draft,
                sources=planning_draft.sources,
                llm_client=llm_client,
            )
            if event_sink:
                event_sink.record_dataclass(
                    stage="industry_diligence",
                    event_type="artifact",
                    title="Industry due diligence completed",
                    payload=industry_report,
                    actor="industry_diligence",
                )
            if run_id:
                self.store.save_artifact(run_id, "industry_report", "Industry Due Diligence", asdict(industry_report))

        if classification.needs_macro_report:
            macro_selection = select_macro_metrics(question)
            metric_selections.append(macro_selection)
            if event_sink:
                event_sink.record_dataclass(
                    stage="metric_selection",
                    event_type="selection",
                    title="Selected macro diligence metrics",
                    payload=macro_selection,
                    actor="macro_diligence",
                )
            economic_report = build_economic_overview(
                metric_selection=macro_selection,
                macro_data_client=macro_data_client,
                llm_client=llm_client,
            )
            if event_sink:
                event_sink.record_dataclass(
                    stage="economic_overview",
                    event_type="artifact",
                    title="Economic overview completed",
                    payload=economic_report,
                    actor="macro_diligence",
                )
            if run_id:
                self.store.save_artifact(run_id, "economic_report", "Economic Overview", asdict(economic_report))

        diligence_packet = DueDiligencePacket(
            classification=classification,
            metric_selections=metric_selections,
            technical_report=technical_report,
            stock_report=stock_report,
            economic_report=economic_report,
            industry_report=industry_report,
        )

        blocked_reason = None
        if technical_review_rounds and not technical_review_rounds[-1].passes:
            blocked_reason = (
                "Technical review blocked the investor panel because the report was not yet deep or source-backed enough."
            )
            if event_sink:
                event_sink.record(
                    stage="technical_review",
                    event_type="blocked",
                    title="Technical review blocked the run",
                    payload={
                        "blocked_reason": blocked_reason,
                        "required_revisions": technical_review_rounds[-1].required_revisions,
                    },
                    actor="technical_reviewer",
                )
            result = RunResult(
                question=question,
                context=context,
                classification=classification,
                planning_draft=planning_draft,
                diligence_packet=diligence_packet,
                technical_review_rounds=technical_review_rounds,
                analyses=[],
                cross_examinations=[],
                committee_memo=None,
                committee_reasoning=[],
                discussion_log=[],
                proposals=[],
                votes=[],
                follow_up_rounds_used=0,
                final_disposition="no_invest",
                blocked_reason=blocked_reason,
                run_id=run_id,
                prompt_snapshot=prompt_snapshot or planning_draft.prompt_pack,
                transcript=list(event_sink.events) if event_sink else [],
            )
            if event_sink:
                event_sink.record(
                    stage="moderator",
                    event_type="completed",
                    title="Run finished after technical-review block",
                    payload={"proposal_count": 0, "vote_count": 0, "disposition": "no_invest"},
                    actor="moderator",
                )
                result.transcript = list(event_sink.events)
            return result

        analyses, cross_examinations, committee_memo, committee_reasoning, discussion_log, proposals, votes, rounds_used, disposition = run_investor_debate(
            knowledge_base=knowledge_base,
            investors=knowledge_base.investor_profiles,
            packet=diligence_packet,
            planning_draft=planning_draft,
            company=company,
            market_data_client=market_data_client,
            macro_data_client=macro_data_client,
            event_sink=event_sink,
        )

        result = RunResult(
            question=question,
            context=context,
            classification=classification,
            planning_draft=planning_draft,
            diligence_packet=diligence_packet,
            technical_review_rounds=technical_review_rounds,
            analyses=analyses,
            cross_examinations=cross_examinations,
            committee_memo=committee_memo,
            committee_reasoning=committee_reasoning,
            discussion_log=discussion_log,
            proposals=proposals,
            votes=votes,
            follow_up_rounds_used=rounds_used,
            final_disposition=disposition,
            blocked_reason=blocked_reason,
            run_id=run_id,
            prompt_snapshot=prompt_snapshot or planning_draft.prompt_pack,
            transcript=list(event_sink.events) if event_sink else [],
        )

        if event_sink:
            event_sink.record(
                stage="moderator",
                event_type="completed",
                title="Run finished and ready for artifact export",
                payload={
                    "proposal_count": len(result.proposals),
                    "vote_count": len(result.votes),
                    "final_disposition": result.final_disposition,
                },
                actor="moderator",
            )
            result.transcript = list(event_sink.events)
        return result

    def execute_run(
        self,
        question: str,
        context: str = "",
        run_id: str | None = None,
        output_dir: Path | None = None,
        planning_draft: PlanningDraft | None = None,
    ) -> RunResult:
        approved_draft = planning_draft
        persisted_run_id = run_id
        if approved_draft is None:
            draft = self.generate_plan(question=question, context=context)
            persisted_run_id = persisted_run_id or self.store.create_run(question=question, context=context)
            approved_draft = approve_planning_draft(draft, run_id=persisted_run_id)
            self.store.save_planning_draft(approved_draft)
            self.store.link_plan_to_run(approved_draft.plan_id, persisted_run_id, approved_draft.approved_at or _now())
        else:
            persisted_run_id = persisted_run_id or approved_draft.run_id or self.store.create_run(question=question, context=context)
            if approved_draft.status != "APPROVED" or approved_draft.run_id != persisted_run_id:
                approved_draft = approve_planning_draft(approved_draft, run_id=persisted_run_id)
                self.store.save_planning_draft(approved_draft)
            self.store.link_plan_to_run(approved_draft.plan_id, persisted_run_id, approved_draft.approved_at or _now())

        event_sink = RunEventSink(run_id=persisted_run_id, store=self.store)
        event_sink.record(
            stage="question",
            event_type="submitted",
            title="Question submitted",
            payload={"question": question, "context": context},
            actor="user",
        )

        try:
            result = self.ask(
                question=question,
                context=context,
                planning_draft=approved_draft,
                run_id=persisted_run_id,
                prompt_snapshot=approved_draft.prompt_pack,
                event_sink=event_sink,
            )
            result.run_id = persisted_run_id
            result.prompt_snapshot = approved_draft.prompt_pack
            result.transcript = list(event_sink.events)

            target_dir = output_dir if output_dir else build_report_output_dir(self.config.outputs_dir, result)
            markdown_path = (target_dir / "investorcrew_report.md").resolve()
            json_path = (target_dir / "investorcrew_report.json").resolve()
            result.saved_markdown_path = str(markdown_path)
            result.saved_json_path = str(json_path)

            markdown = render_markdown(result)
            json_output = render_json(result)
            save_run_artifacts(
                result=result,
                markdown=markdown,
                json_output=json_output,
                outputs_dir=self.config.outputs_dir,
                explicit_output_dir=target_dir,
            )
            self.store.complete_run(
                run_id=persisted_run_id,
                result=result,
                markdown_path=result.saved_markdown_path,
                json_path=result.saved_json_path,
            )
            return result
        except Exception as exc:
            self.store.fail_run(persisted_run_id, str(exc))
            raise

    def create_run(self, question: str, context: str = "") -> str:
        run_id, approved_draft = self.queue_run(question=question, context=context)
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.store.get_run(run_id)

    def get_run_events(self, run_id: str) -> list[dict[str, Any]]:
        return self.store.list_run_events(run_id)

    def list_companies(self, search: str | None = None) -> list[dict[str, Any]]:
        return self.store.list_companies(search=search)

    def get_company_detail(self, ticker: str) -> dict[str, Any]:
        return self.store.get_company_detail(ticker)

    def list_company_reports(self, ticker: str) -> list[dict[str, Any]]:
        return self.store.list_reports_for_company(ticker)

    def get_report_detail(self, run_id: str) -> dict[str, Any]:
        return self.store.get_report_detail(run_id)

    def list_investors(self) -> list[dict[str, Any]]:
        return [asdict(profile) for profile in self.store.fetch_investor_profiles()]

    def update_investor(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.update_investor_profile(slug, payload)

    def list_prompts(self) -> list[dict[str, Any]]:
        return self.store.list_prompt_templates()

    def update_prompt(self, key: str, content: str, label: str | None = None, description: str | None = None) -> dict[str, Any]:
        return self.store.update_prompt_template(key, label, description, content)

    def list_settings(self) -> list[dict[str, Any]]:
        return self.store.list_settings()

    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        return self.store.update_setting(key, value)

    def update_company(self, ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.upsert_company_payload(ticker, payload)

    def generate_self_review(self, run_id: str) -> dict[str, Any]:
        report = self.store.get_run(run_id)
        final_result = report.get("final_result")
        if not final_result:
            raise ValueError(f"Run {run_id} is not completed yet")
        review = build_self_review(
            run_id=run_id,
            result_payload=final_result,
            prompt_snapshot=report.get("prompt_snapshot", {}),
        )
        self.store.save_self_review(review)
        return {
            "review_id": review.review_id,
            "run_id": review.run_id,
            "summary": review.summary,
            "recommendations": [asdict(item) for item in review.recommendations],
            "created_at": review.created_at,
        }
