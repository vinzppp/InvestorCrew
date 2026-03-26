from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from investorcrew.artifacts import build_report_output_dir, save_run_artifacts
from investorcrew.classification import classify_question
from investorcrew.config import AppConfig
from investorcrew.data_store import KnowledgeBase
from investorcrew.debate import run_investor_debate
from investorcrew.diligence import build_economic_overview, build_stock_due_diligence, build_technical_due_diligence
from investorcrew.events import RunEventSink
from investorcrew.metric_selection import select_company_metrics, select_macro_metrics, select_technology_metrics
from investorcrew.models import DueDiligencePacket, MetricSelection, RunResult
from investorcrew.providers import build_llm_client, build_macro_data_client, build_market_data_client
from investorcrew.render import render_json, render_markdown
from investorcrew.review import build_self_review
from investorcrew.store import SqliteStore


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

    def ask(
        self,
        question: str,
        context: str = "",
        run_id: str | None = None,
        prompt_snapshot: dict[str, str] | None = None,
        event_sink: RunEventSink | None = None,
    ) -> RunResult:
        knowledge_base = self.store.load_runtime_knowledge_base()
        company = knowledge_base.find_company(f"{question}\n{context}")
        if company is None:
            seed_company = self.seed_knowledge_base.ensure_company_fixture(question=question, context=context)
            if seed_company is not None:
                self.store.upsert_company_record(seed_company)
                knowledge_base = self.store.load_runtime_knowledge_base()
                company = knowledge_base.find_company(seed_company.ticker)
                if event_sink:
                    event_sink.record(
                        stage="company_lookup",
                        event_type="fixture_created",
                        title=f"Created placeholder fixture for {seed_company.ticker}",
                        payload={"ticker": seed_company.ticker, "name": seed_company.name},
                        actor="system",
                    )

        llm_client = build_llm_client(self.config)
        market_data_client = build_market_data_client(self.config, knowledge_base)
        macro_data_client = build_macro_data_client(self.config, knowledge_base)

        classification = classify_question(question, context, company)
        if event_sink:
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
                llm_client=llm_client,
            )
            if event_sink:
                event_sink.record_dataclass(
                    stage="technical_diligence",
                    event_type="artifact",
                    title="Technical due diligence completed",
                    payload=technical_report,
                    actor="technical_diligence",
                )
            if run_id:
                self.store.save_artifact(run_id, "technical_report", "Technical Due Diligence", asdict(technical_report))

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
        )

        analyses, cross_examinations, proposals, votes, rounds_used = run_investor_debate(
            knowledge_base=knowledge_base,
            investors=knowledge_base.investor_profiles,
            packet=diligence_packet,
            company=company,
            market_data_client=market_data_client,
            macro_data_client=macro_data_client,
            event_sink=event_sink,
        )

        result = RunResult(
            question=question,
            context=context,
            classification=classification,
            diligence_packet=diligence_packet,
            analyses=analyses,
            cross_examinations=cross_examinations,
            proposals=proposals,
            votes=votes,
            follow_up_rounds_used=rounds_used,
            run_id=run_id,
            prompt_snapshot=prompt_snapshot or {},
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
    ) -> RunResult:
        persisted_run_id = run_id or self.store.create_run(question=question, context=context)
        prompt_snapshot = self.store.get_prompt_snapshot()
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
                run_id=persisted_run_id,
                prompt_snapshot=prompt_snapshot,
                event_sink=event_sink,
            )
            result.run_id = persisted_run_id
            result.prompt_snapshot = prompt_snapshot
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
        return self.store.create_run(question=question, context=context)

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
