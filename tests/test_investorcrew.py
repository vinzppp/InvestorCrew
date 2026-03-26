from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from investorcrew.classification import classify_question
from investorcrew.config import AppConfig
from investorcrew.data_store import KnowledgeBase
from investorcrew.metric_selection import select_company_metrics, select_macro_metrics
from investorcrew.service import InvestorCrewService

try:
    from fastapi.testclient import TestClient

    from investorcrew.api import create_app

    HAS_FASTAPI = True
except Exception:
    HAS_FASTAPI = False


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


class InvestorCrewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.tempdir.name)
        self.data_dir = self.temp_path / "data"
        shutil.copytree(DATA_DIR, self.data_dir)
        self.outputs_dir = self.temp_path / "outputs"
        self.db_path = self.temp_path / "runtime" / "investorcrew.db"
        self.config = AppConfig(
            data_dir=self.data_dir,
            db_path=self.db_path,
            outputs_dir=self.outputs_dir,
            llm_provider="heuristic",
            llm_model="gpt-5.4-mini",
            openai_api_key=None,
            openai_base_url="https://api.openai.com/v1",
            market_data_provider="fixture",
            macro_data_provider="fixture",
        )
        self.service = InvestorCrewService(config=self.config)
        self.knowledge_base = KnowledgeBase(self.data_dir)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_investor_profiles_validate(self) -> None:
        profiles = self.knowledge_base.investor_profiles
        self.assertEqual(len(profiles), 10)
        self.assertEqual(profiles[0].name, "Benjamin Graham")

    def test_public_tech_company_classifies_as_mixed(self) -> None:
        company = self.knowledge_base.find_company("Should I buy NVIDIA stock given AI demand?")
        classification = classify_question("Should I buy NVIDIA stock given AI demand?", "", company)
        self.assertEqual(classification.category, "mixed")
        self.assertTrue(classification.needs_technology_report)
        self.assertTrue(classification.needs_stock_report)

    def test_company_metric_selection_excludes_pb_for_tech(self) -> None:
        company = self.knowledge_base.companies["NVDA"]
        selection = select_company_metrics(company)
        self.assertIn("ev_to_sales", selection.chosen_metrics)
        self.assertIn("price_to_book", selection.excluded_metrics)

    def test_bank_metric_selection_excludes_ev_sales(self) -> None:
        company = self.knowledge_base.companies["JPM"]
        selection = select_company_metrics(company)
        self.assertIn("price_to_tangible_book", selection.chosen_metrics)
        self.assertIn("ev_to_sales", selection.excluded_metrics)

    def test_oklo_metric_selection_uses_pre_revenue_nuclear_metrics(self) -> None:
        company = self.knowledge_base.companies["OKLO"]
        selection = select_company_metrics(company)
        self.assertIn("cash_billion", selection.chosen_metrics)
        self.assertIn("price_to_book", selection.chosen_metrics)
        self.assertIn("ev_to_ebitda", selection.excluded_metrics)

    def test_macro_lens_selection_changes_for_inflation_prompt(self) -> None:
        selection = select_macro_metrics("What do inflation, rates, and markets say about global stocks?")
        self.assertIn("cpi_yoy_pct", selection.chosen_metrics)
        self.assertIn("forward_pe", selection.chosen_metrics)
        self.assertIn("market_conditions", selection.lens)

    def test_investor_analyses_have_six_stages(self) -> None:
        result = self.service.ask("Should I buy NVIDIA stock given AI demand and the current market setup?")
        self.assertEqual(len(result.analyses), 10)
        for analysis in result.analyses:
            self.assertTrue(analysis.situation)
            self.assertTrue(analysis.interpretation)
            self.assertTrue(analysis.thesis)
            self.assertTrue(analysis.falsification)
            self.assertTrue(analysis.portfolio)
            self.assertTrue(analysis.conclusion)

    def test_follow_up_loop_stops_after_two_rounds(self) -> None:
        result = self.service.ask("Should I buy NVIDIA stock given AI demand and macro conditions?")
        self.assertEqual(result.follow_up_rounds_used, 2)
        self.assertLessEqual(result.follow_up_rounds_used, 2)
        self.assertTrue(result.diligence_packet.supplemental_notes)

    def test_synthesis_caps_proposals_and_vote_matrix_complete(self) -> None:
        result = self.service.ask("How should I think about markets and the economy today?")
        self.assertLessEqual(len(result.proposals), 3)
        expected_votes = len(result.proposals) * 10
        self.assertEqual(len(result.votes), expected_votes)

    def test_result_serializes_to_json(self) -> None:
        result = self.service.ask("Should I buy JPM stock?")
        payload = result.to_dict()
        self.assertEqual(payload["classification"]["category"], "stock")
        json.dumps(payload)

    def test_unknown_stock_question_creates_placeholder_fixture(self) -> None:
        placeholder_path = self.data_dir / "fixtures" / "companies" / "oklo.json"
        if placeholder_path.exists():
            placeholder_path.unlink()
        config = AppConfig(
            data_dir=self.data_dir,
            db_path=self.temp_path / "runtime" / "placeholder.db",
            outputs_dir=self.outputs_dir,
            llm_provider="heuristic",
            llm_model="gpt-5.4-mini",
            openai_api_key=None,
            openai_base_url="https://api.openai.com/v1",
            market_data_provider="fixture",
            macro_data_provider="fixture",
        )
        service = InvestorCrewService(config=config)
        result = service.ask("What do you think about investing in OKLO stock (nuclear company)?")
        self.assertEqual(result.classification.category, "mixed")
        self.assertIsNotNone(result.diligence_packet.stock_report)
        self.assertIsNotNone(result.diligence_packet.technical_report)
        self.assertTrue(placeholder_path.exists())
        self.assertEqual(result.diligence_packet.stock_report.ticker, "OKLO")

    def test_execute_run_persists_transcript_and_report_detail(self) -> None:
        result = self.service.execute_run("Should I buy JPM stock?")
        self.assertIsNotNone(result.run_id)
        self.assertTrue(result.saved_markdown_path)
        self.assertTrue(Path(result.saved_markdown_path or "").exists())
        self.assertTrue(result.transcript)

        run = self.service.get_run(result.run_id or "")
        self.assertEqual(run["status"], "COMPLETED")

        events = self.service.get_run_events(result.run_id or "")
        self.assertTrue(events)
        self.assertEqual(events[0]["stage"], "question")

        detail = self.service.get_report_detail(result.run_id or "")
        self.assertTrue(detail["events"])
        self.assertTrue(detail["artifacts"])
        self.assertTrue(detail["markdown_content"])

    def test_generate_self_review_persists_review(self) -> None:
        result = self.service.execute_run("Should I buy NVIDIA stock given AI demand and market conditions?")
        review = self.service.generate_self_review(result.run_id or "")
        self.assertEqual(review["run_id"], result.run_id)
        self.assertTrue(review["recommendations"])

        detail = self.service.get_report_detail(result.run_id or "")
        self.assertEqual(detail["self_reviews"][0]["review_id"], review["review_id"])

    def test_cli_writes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "report"
            env = {
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "INVESTORCREW_DATA_DIR": str(self.data_dir),
                "INVESTORCREW_DB_PATH": str(self.temp_path / "runtime" / "cli.db"),
                "INVESTORCREW_OUTPUTS_DIR": str(self.outputs_dir),
            }
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "investorcrew",
                    "ask",
                    "--question",
                    "Should I buy JPM stock?",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            markdown_path = (output_dir / "investorcrew_report.md").resolve()
            json_path = (output_dir / "investorcrew_report.json").resolve()
            self.assertIn("# InvestorCrew Memo", completed.stdout)
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn(str(markdown_path), completed.stdout)
            self.assertIn(str(json_path), completed.stdout)

    def test_cli_auto_saves_without_output_dir(self) -> None:
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "INVESTORCREW_DATA_DIR": str(self.data_dir),
            "INVESTORCREW_DB_PATH": str(self.temp_path / "runtime" / "cli-auto.db"),
            "INVESTORCREW_OUTPUTS_DIR": str(self.outputs_dir),
        }
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "investorcrew",
                "ask",
                "--question",
                "Should I buy JPM stock?",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        markdown_paths = list(self.outputs_dir.glob("jpm/*/investorcrew_report.md"))
        json_paths = list(self.outputs_dir.glob("jpm/*/investorcrew_report.json"))
        self.assertEqual(len(markdown_paths), 1)
        self.assertEqual(len(json_paths), 1)
        self.assertIn(str(markdown_paths[0].resolve()), completed.stdout)
        self.assertIn(str(json_paths[0].resolve()), completed.stdout)

    @unittest.skipUnless(HAS_FASTAPI, "FastAPI dependencies are not installed")
    def test_api_run_and_self_review_endpoints(self) -> None:
        with patch.dict(
            os.environ,
            {
                "INVESTORCREW_DATA_DIR": str(self.data_dir),
                "INVESTORCREW_DB_PATH": str(self.temp_path / "runtime" / "api.db"),
                "INVESTORCREW_OUTPUTS_DIR": str(self.outputs_dir / "api"),
            },
            clear=False,
        ):
            client = TestClient(create_app())
            companies = client.get("/api/companies")
            self.assertEqual(companies.status_code, 200)
            self.assertTrue(any(item["ticker"] == "NVDA" for item in companies.json()["items"]))

            created = client.post("/api/runs", json={"question": "Should I buy JPM stock?", "context": ""})
            self.assertEqual(created.status_code, 200)
            run = created.json()

            status = run["status"]
            for _ in range(80):
                if status in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(0.05)
                status = client.get(f"/api/runs/{run['id']}").json()["status"]
            self.assertEqual(status, "COMPLETED")

            events = client.get(f"/api/runs/{run['id']}/events")
            self.assertEqual(events.status_code, 200)
            self.assertTrue(events.json()["items"])

            report = client.get(f"/api/reports/{run['id']}")
            self.assertEqual(report.status_code, 200)
            self.assertTrue(report.json()["run"]["final_result"])

            review = client.post(f"/api/reports/{run['id']}/self-review")
            self.assertEqual(review.status_code, 200)
            self.assertEqual(review.json()["run_id"], run["id"])


if __name__ == "__main__":
    unittest.main()
