from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from investorcrew.data_store import KnowledgeBase
from investorcrew.models import (
    CommentarySnapshot,
    CompanyRecord,
    HoldingsSnapshot,
    InvestorProfile,
    ReportEvent,
    RunResult,
    SelfReview,
    SelfReviewRecommendation,
)
from investorcrew.prompts import DEFAULT_PROMPT_TEMPLATES, DEFAULT_SETTINGS


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DatabaseKnowledgeBase:
    def __init__(self, store: "SqliteStore") -> None:
        self.store = store

    @property
    def investor_profiles(self) -> list[InvestorProfile]:
        return self.store.fetch_investor_profiles()

    @property
    def companies(self) -> dict[str, CompanyRecord]:
        return {company.ticker: company for company in self.store.fetch_company_records()}

    @property
    def macro_record(self):
        return KnowledgeBase(self.store.seed_data_dir).macro_record

    def find_company(self, text: str) -> CompanyRecord | None:
        lowered = text.lower()
        matches: list[tuple[int, CompanyRecord]] = []
        for company in self.companies.values():
            for alias in company.aliases + [company.ticker.lower(), company.name.lower()]:
                if alias in lowered:
                    matches.append((len(alias), company))
                    break
        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[0][1]

    def metric_value_for_company(self, company: CompanyRecord, metric: str) -> Any | None:
        stock = company.stock
        if metric in stock and stock.get(metric) is not None:
            return stock.get(metric)
        for section in ("operating_metrics", "valuation_metrics", "balance_sheet_metrics", "supplemental_metrics"):
            value = stock.get(section, {}).get(metric)
            if value is not None:
                return value
        return None

    def merge_company_metrics(self, company: CompanyRecord, updates: dict[str, Any]) -> None:
        for metric, value in updates.items():
            if metric in company.stock.get("operating_metrics", {}):
                company.stock["operating_metrics"][metric] = value
            elif metric in company.stock.get("valuation_metrics", {}):
                company.stock["valuation_metrics"][metric] = value
            elif metric in company.stock.get("balance_sheet_metrics", {}):
                company.stock["balance_sheet_metrics"][metric] = value
            else:
                company.stock.setdefault("supplemental_metrics", {})[metric] = value
        self.store.upsert_company_record(company)


class SqliteStore:
    def __init__(self, db_path: Path, seed_data_dir: Path, outputs_dir: Path) -> None:
        self.db_path = db_path
        self.seed_data_dir = seed_data_dir
        self.outputs_dir = outputs_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    ticker TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    is_public INTEGER NOT NULL,
                    is_tech INTEGER NOT NULL,
                    sector TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    archetype TEXT NOT NULL,
                    description TEXT NOT NULL,
                    technology_json TEXT NOT NULL,
                    stock_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS company_aliases (
                    ticker TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    PRIMARY KEY (ticker, alias)
                );
                CREATE TABLE IF NOT EXISTS investors (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    key TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    description TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS config_revisions (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    previous_value_json TEXT,
                    new_value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    context TEXT NOT NULL,
                    company_ticker TEXT,
                    company_name TEXT,
                    status TEXT NOT NULL,
                    classification_json TEXT,
                    final_result_json TEXT,
                    prompt_snapshot_json TEXT,
                    markdown_path TEXT,
                    json_path TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dd_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    investor_name TEXT NOT NULL,
                    vote TEXT NOT NULL,
                    rationale TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS self_reviews (
                    review_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    recommendations_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
        self.bootstrap()

    def bootstrap(self) -> None:
        seed = KnowledgeBase(self.seed_data_dir)
        for company in seed.companies.values():
            self.upsert_company_record(company)
        for profile in seed.investor_profiles:
            self.upsert_investor_profile(profile)
        for template in DEFAULT_PROMPT_TEMPLATES:
            self.upsert_prompt_template(template["key"], template["label"], template["description"], template["content"])
        for setting in DEFAULT_SETTINGS:
            self.upsert_setting(setting["key"], setting["value"])
        self.import_existing_outputs()

    def load_runtime_knowledge_base(self) -> DatabaseKnowledgeBase:
        return DatabaseKnowledgeBase(self)

    def upsert_company_record(self, company: CompanyRecord) -> None:
        timestamp = _now()
        aliases = list(dict.fromkeys(alias.lower() for alias in company.aliases))
        with self.connect() as connection:
            existing = connection.execute("SELECT created_at FROM companies WHERE ticker = ?", (company.ticker,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            connection.execute(
                """
                INSERT INTO companies (
                    ticker, name, aliases_json, is_public, is_tech, sector, industry, archetype,
                    description, technology_json, stock_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    aliases_json = excluded.aliases_json,
                    is_public = excluded.is_public,
                    is_tech = excluded.is_tech,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    archetype = excluded.archetype,
                    description = excluded.description,
                    technology_json = excluded.technology_json,
                    stock_json = excluded.stock_json,
                    updated_at = excluded.updated_at
                """,
                (
                    company.ticker,
                    company.name,
                    json.dumps(aliases),
                    int(company.is_public),
                    int(company.is_tech),
                    company.sector,
                    company.industry,
                    company.archetype,
                    company.description,
                    json.dumps(company.technology),
                    json.dumps(company.stock),
                    created_at,
                    timestamp,
                ),
            )
            connection.execute("DELETE FROM company_aliases WHERE ticker = ?", (company.ticker,))
            connection.executemany(
                "INSERT OR REPLACE INTO company_aliases (ticker, alias) VALUES (?, ?)",
                [(company.ticker, alias) for alias in aliases],
            )

    def upsert_company_payload(self, ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
        company = self.get_company_record(ticker)
        if company is None:
            raise KeyError(f"Unknown company: {ticker}")
        raw = {
            "ticker": company.ticker,
            "name": payload.get("name", company.name),
            "aliases": payload.get("aliases", company.aliases),
            "is_public": payload.get("is_public", company.is_public),
            "is_tech": payload.get("is_tech", company.is_tech),
            "sector": payload.get("sector", company.sector),
            "industry": payload.get("industry", company.industry),
            "archetype": payload.get("archetype", company.archetype),
            "description": payload.get("description", company.description),
            "technology": payload.get("technology", company.technology),
            "stock": payload.get("stock", company.stock),
        }
        previous = self.serialize_company_record(company)
        self.upsert_company_record(self._company_from_raw(raw))
        self.insert_config_revision("company", ticker, previous, raw)
        return raw

    def fetch_company_records(self) -> list[CompanyRecord]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM companies ORDER BY ticker").fetchall()
        return [self._company_from_row(row) for row in rows]

    def get_company_record(self, ticker: str) -> CompanyRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM companies WHERE ticker = ?", (ticker.upper(),)).fetchone()
        return self._company_from_row(row) if row else None

    def upsert_investor_profile(self, profile: InvestorProfile) -> None:
        timestamp = _now()
        payload = asdict(profile)
        with self.connect() as connection:
            existing = connection.execute("SELECT created_at FROM investors WHERE slug = ?", (profile.slug,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            connection.execute(
                """
                INSERT INTO investors (slug, name, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (profile.slug, profile.name, json.dumps(payload), created_at, timestamp),
            )

    def fetch_investor_profiles(self) -> list[InvestorProfile]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM investors ORDER BY name").fetchall()
        profiles = []
        for row in rows:
            raw = json.loads(row["payload_json"])
            profiles.append(
                InvestorProfile(
                    name=raw["name"],
                    slug=raw["slug"],
                    style_tags=list(raw["style_tags"]),
                    philosophy=raw["philosophy"],
                    preferred_metrics=list(raw["preferred_metrics"]),
                    heuristics=list(raw["heuristics"]),
                    risk_rules=list(raw["risk_rules"]),
                    portfolio_habits=list(raw["portfolio_habits"]),
                    commentary_snapshots=[CommentarySnapshot(**item) for item in raw["commentary_snapshots"]],
                    holdings_snapshots=[HoldingsSnapshot(**item) for item in raw["holdings_snapshots"]],
                    blind_spots=list(raw["blind_spots"]),
                    debate_role=raw["debate_role"],
                )
            )
        return profiles

    def update_investor_profile(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM investors WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown investor: {slug}")
        previous = json.loads(row["payload_json"])
        merged = {**previous, **payload, "slug": slug}
        profile = InvestorProfile(
            name=merged["name"],
            slug=merged["slug"],
            style_tags=list(merged["style_tags"]),
            philosophy=merged["philosophy"],
            preferred_metrics=list(merged["preferred_metrics"]),
            heuristics=list(merged["heuristics"]),
            risk_rules=list(merged["risk_rules"]),
            portfolio_habits=list(merged["portfolio_habits"]),
            commentary_snapshots=[CommentarySnapshot(**item) for item in merged["commentary_snapshots"]],
            holdings_snapshots=[HoldingsSnapshot(**item) for item in merged["holdings_snapshots"]],
            blind_spots=list(merged["blind_spots"]),
            debate_role=merged["debate_role"],
        )
        self.upsert_investor_profile(profile)
        self.insert_config_revision("investor", slug, previous, merged)
        return merged

    def upsert_prompt_template(self, key: str, label: str, description: str, content: str) -> None:
        timestamp = _now()
        with self.connect() as connection:
            existing = connection.execute("SELECT created_at FROM prompt_templates WHERE key = ?", (key,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            connection.execute(
                """
                INSERT INTO prompt_templates (key, label, description, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    label = excluded.label,
                    description = excluded.description,
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (key, label, description, content, created_at, timestamp),
            )

    def list_prompt_templates(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM prompt_templates ORDER BY key").fetchall()
        return [dict(row) for row in rows]

    def get_prompt_snapshot(self) -> dict[str, str]:
        return {row["key"]: row["content"] for row in self.list_prompt_templates()}

    def update_prompt_template(self, key: str, label: str | None, description: str | None, content: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM prompt_templates WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown prompt template: {key}")
        previous = dict(row)
        updated = {
            "key": key,
            "label": label or row["label"],
            "description": description or row["description"],
            "content": content,
        }
        self.upsert_prompt_template(updated["key"], updated["label"], updated["description"], updated["content"])
        self.insert_config_revision("prompt_template", key, previous, updated)
        return updated

    def upsert_setting(self, key: str, value: Any) -> None:
        timestamp = _now()
        value_json = json.dumps(value)
        with self.connect() as connection:
            existing = connection.execute("SELECT created_at FROM settings WHERE key = ?", (key,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            connection.execute(
                """
                INSERT INTO settings (key, value_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, value_json, created_at, timestamp),
            )

    def list_settings(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM settings ORDER BY key").fetchall()
        return [{"key": row["key"], "value": json.loads(row["value_json"])} for row in rows]

    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
        previous = json.loads(row["value_json"]) if row else None
        self.upsert_setting(key, value)
        self.insert_config_revision("setting", key, previous, value)
        return {"key": key, "value": value}

    def insert_config_revision(self, entity_type: str, entity_key: str, previous_value: Any, new_value: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO config_revisions (id, entity_type, entity_key, previous_value_json, new_value_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    entity_type,
                    entity_key,
                    json.dumps(previous_value) if previous_value is not None else None,
                    json.dumps(new_value),
                    _now(),
                ),
            )

    def create_run(self, question: str, context: str) -> str:
        run_id = str(uuid.uuid4())
        timestamp = _now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (id, question, context, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, question, context, "QUEUED", timestamp, timestamp),
            )
        return run_id

    def mark_run_running(self, run_id: str, company_ticker: str | None = None, company_name: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'RUNNING', company_ticker = ?, company_name = ?, updated_at = ?
                WHERE id = ?
                """,
                (company_ticker, company_name, _now(), run_id),
            )

    def save_event(
        self,
        run_id: str,
        sequence: int,
        stage: str,
        event_type: str,
        title: str,
        actor: str | None,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO run_events (run_id, sequence, stage, event_type, actor, title, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, sequence, stage, event_type, actor, title, json.dumps(payload), created_at),
            )

    def save_artifact(self, run_id: str, artifact_type: str, title: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dd_artifacts (run_id, artifact_type, title, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, artifact_type, title, json.dumps(payload), _now()),
            )

    def complete_run(
        self,
        run_id: str,
        result: RunResult,
        markdown_path: str,
        json_path: str,
    ) -> None:
        result_dict = result.to_dict()
        with self.connect() as connection:
            connection.execute("DELETE FROM proposals WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM votes WHERE run_id = ?", (run_id,))
            connection.execute(
                """
                UPDATE runs
                SET status = 'COMPLETED',
                    company_ticker = ?,
                    company_name = ?,
                    classification_json = ?,
                    final_result_json = ?,
                    prompt_snapshot_json = ?,
                    markdown_path = ?,
                    json_path = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    result.classification.company_ticker,
                    result.classification.company_name,
                    json.dumps(asdict(result.classification)),
                    json.dumps(result_dict),
                    json.dumps(result.prompt_snapshot),
                    markdown_path,
                    json_path,
                    _now(),
                    _now(),
                    run_id,
                ),
            )
            for proposal in result.proposals:
                connection.execute(
                    """
                    INSERT INTO proposals (run_id, proposal_id, title, action, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, proposal.proposal_id, proposal.title, proposal.action, json.dumps(asdict(proposal))),
                )
            for vote in result.votes:
                connection.execute(
                    """
                    INSERT INTO votes (run_id, proposal_id, investor_name, vote, rationale)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, vote.proposal_id, vote.investor_name, vote.vote, vote.rationale),
                )

    def fail_run(self, run_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE runs SET status = 'FAILED', error = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (error, _now(), _now(), run_id),
            )

    def list_run_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY sequence", (run_id,)).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "stage": row["stage"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "title": row["title"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_companies(self, search: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if search:
                term = f"%{search.lower()}%"
                rows = connection.execute(
                    """
                    SELECT c.*, COUNT(r.id) AS report_count, MAX(r.created_at) AS last_report_at
                    FROM companies c
                    LEFT JOIN runs r ON r.company_ticker = c.ticker
                    WHERE lower(c.ticker) LIKE ? OR lower(c.name) LIKE ?
                    GROUP BY c.ticker
                    ORDER BY c.name
                    """,
                    (term, term),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT c.*, COUNT(r.id) AS report_count, MAX(r.created_at) AS last_report_at
                    FROM companies c
                    LEFT JOIN runs r ON r.company_ticker = c.ticker
                    GROUP BY c.ticker
                    ORDER BY c.name
                    """
                ).fetchall()
        return [
            {
                "id": row["ticker"],
                "ticker": row["ticker"],
                "name": row["name"],
                "sector": row["sector"],
                "industry": row["industry"],
                "archetype": row["archetype"],
                "is_tech": bool(row["is_tech"]),
                "report_count": row["report_count"] or 0,
                "last_report_at": row["last_report_at"],
            }
            for row in rows
        ]

    def get_company_detail(self, ticker: str) -> dict[str, Any]:
        company = self.get_company_record(ticker)
        if company is None:
            raise KeyError(f"Unknown company: {ticker}")
        return {
            "company": self.serialize_company_record(company),
            "reports": self.list_reports_for_company(ticker),
        }

    def list_reports_for_company(self, ticker: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, question, status, company_ticker, company_name, created_at, completed_at, markdown_path, json_path
                FROM runs
                WHERE company_ticker = ?
                ORDER BY created_at DESC
                """,
                (ticker.upper(),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown run: {run_id}")
        payload = dict(row)
        payload["classification"] = json.loads(row["classification_json"]) if row["classification_json"] else None
        payload["final_result"] = json.loads(row["final_result_json"]) if row["final_result_json"] else None
        payload["prompt_snapshot"] = json.loads(row["prompt_snapshot_json"]) if row["prompt_snapshot_json"] else {}
        return payload

    def get_report_detail(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        with self.connect() as connection:
            artifacts = connection.execute(
                "SELECT artifact_type, title, payload_json, created_at FROM dd_artifacts WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            proposals = connection.execute(
                "SELECT proposal_id, title, action, payload_json FROM proposals WHERE run_id = ? ORDER BY proposal_id",
                (run_id,),
            ).fetchall()
            votes = connection.execute(
                "SELECT proposal_id, investor_name, vote, rationale FROM votes WHERE run_id = ? ORDER BY proposal_id, investor_name",
                (run_id,),
            ).fetchall()
        markdown_content = None
        if run.get("markdown_path"):
            path = Path(run["markdown_path"])
            if path.exists():
                markdown_content = path.read_text()
        return {
            "run": run,
            "events": self.list_run_events(run_id),
            "artifacts": [
                {
                    "artifact_type": row["artifact_type"],
                    "title": row["title"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                }
                for row in artifacts
            ],
            "proposals": [json.loads(row["payload_json"]) for row in proposals],
            "votes": [dict(row) for row in votes],
            "self_reviews": self.list_self_reviews(run_id),
            "markdown_content": markdown_content,
        }

    def save_self_review(self, review: SelfReview) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO self_reviews (review_id, run_id, summary, recommendations_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    review.review_id,
                    review.run_id,
                    review.summary,
                    json.dumps([asdict(item) for item in review.recommendations]),
                    review.created_at,
                ),
            )

    def list_self_reviews(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM self_reviews WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
        return [
            {
                "review_id": row["review_id"],
                "run_id": row["run_id"],
                "summary": row["summary"],
                "recommendations": json.loads(row["recommendations_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def import_company_fixture(self, ticker: str) -> CompanyRecord:
        path = self.seed_data_dir / "fixtures" / "companies" / f"{ticker.lower()}.json"
        raw = json.loads(path.read_text())
        company = self._company_from_raw(raw)
        self.upsert_company_record(company)
        return company

    def import_existing_outputs(self) -> None:
        if not self.outputs_dir.exists():
            return
        json_paths = sorted(self.outputs_dir.glob("**/investorcrew_report.json"))
        for json_path in json_paths:
            run_id = f"imported-{json_path.parent.name}"
            with self.connect() as connection:
                existing = connection.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone()
            if existing:
                continue
            raw = json.loads(json_path.read_text())
            classification = raw.get("classification") or {}
            created_at = _now()
            markdown_path = json_path.with_name("investorcrew_report.md")
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO runs (
                        id, question, context, company_ticker, company_name, status, classification_json,
                        final_result_json, prompt_snapshot_json, markdown_path, json_path, created_at, updated_at, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'COMPLETED', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        raw.get("question", ""),
                        raw.get("context", ""),
                        classification.get("company_ticker"),
                        classification.get("company_name"),
                        json.dumps(classification),
                        json.dumps(raw),
                        json.dumps(raw.get("prompt_snapshot", {})),
                        str(markdown_path.resolve()) if markdown_path.exists() else None,
                        str(json_path.resolve()),
                        created_at,
                        created_at,
                        created_at,
                    ),
                )
            for index, analysis in enumerate(raw.get("analyses", []), start=1):
                self.save_event(
                    run_id=run_id,
                    sequence=index,
                    stage="imported_analysis",
                    event_type="analysis",
                    title=f"Imported analysis for {analysis.get('investor_name', 'investor')}",
                    actor=analysis.get("investor_name"),
                    payload=analysis,
                    created_at=created_at,
                )
            for proposal in raw.get("proposals", []):
                with self.connect() as connection:
                    connection.execute(
                        "INSERT INTO proposals (run_id, proposal_id, title, action, payload_json) VALUES (?, ?, ?, ?, ?)",
                        (run_id, proposal.get("proposal_id"), proposal.get("title"), proposal.get("action"), json.dumps(proposal)),
                    )
            for vote in raw.get("votes", []):
                with self.connect() as connection:
                    connection.execute(
                        "INSERT INTO votes (run_id, proposal_id, investor_name, vote, rationale) VALUES (?, ?, ?, ?, ?)",
                        (
                            run_id,
                            vote.get("proposal_id"),
                            vote.get("investor_name"),
                            vote.get("vote"),
                            vote.get("rationale"),
                        ),
                    )

    def serialize_company_record(self, company: CompanyRecord) -> dict[str, Any]:
        return {
            "ticker": company.ticker,
            "name": company.name,
            "aliases": company.aliases,
            "is_public": company.is_public,
            "is_tech": company.is_tech,
            "sector": company.sector,
            "industry": company.industry,
            "archetype": company.archetype,
            "description": company.description,
            "technology": company.technology,
            "stock": company.stock,
        }

    def _company_from_row(self, row: sqlite3.Row) -> CompanyRecord:
        return CompanyRecord(
            ticker=row["ticker"],
            name=row["name"],
            aliases=json.loads(row["aliases_json"]),
            is_public=bool(row["is_public"]),
            is_tech=bool(row["is_tech"]),
            sector=row["sector"],
            industry=row["industry"],
            archetype=row["archetype"],
            description=row["description"],
            technology=json.loads(row["technology_json"]),
            stock=json.loads(row["stock_json"]),
        )

    def _company_from_raw(self, raw: dict[str, Any]) -> CompanyRecord:
        return CompanyRecord(
            ticker=raw["ticker"].upper(),
            name=raw["name"],
            aliases=list(raw["aliases"]),
            is_public=bool(raw["is_public"]),
            is_tech=bool(raw["is_tech"]),
            sector=raw["sector"],
            industry=raw["industry"],
            archetype=raw["archetype"],
            description=raw["description"],
            technology=dict(raw["technology"]),
            stock=dict(raw["stock"]),
        )
