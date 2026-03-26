from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path
from typing import Any

from investorcrew.models import (
    CommentarySnapshot,
    CompanyRecord,
    HoldingsSnapshot,
    InvestorProfile,
    MacroRecord,
    ValidationError,
)


REQUIRED_INVESTOR_FIELDS = {
    "name",
    "slug",
    "style_tags",
    "philosophy",
    "preferred_metrics",
    "heuristics",
    "risk_rules",
    "portfolio_habits",
    "commentary_snapshots",
    "holdings_snapshots",
    "blind_spots",
    "debate_role",
}

STOCK_PROMPT_HINTS = (
    "stock",
    "stocks",
    "share",
    "shares",
    "buy",
    "purchase",
    "invest",
    "own",
    "ticker",
)

UPPERCASE_TICKER_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")
COMPANY_NAME_PATTERN = re.compile(
    r"(?:buy|purchase|invest in|own|analyze|review|consider)\s+([A-Za-z][A-Za-z0-9&.\- ]+?)\s+(?:stock|stocks|share|shares)\b",
    re.IGNORECASE,
)

TICKER_STOPWORDS = {"AI", "GDP", "CPI", "PMI", "FED", "USD", "VIX", "EV", "PE"}


class KnowledgeBase:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    @cached_property
    def investor_profiles(self) -> list[InvestorProfile]:
        profiles: list[InvestorProfile] = []
        for path in sorted((self.data_dir / "investors").glob("*.json")):
            raw = json.loads(path.read_text())
            missing = REQUIRED_INVESTOR_FIELDS.difference(raw)
            if missing:
                raise ValidationError(f"{path.name} is missing fields: {sorted(missing)}")
            commentary = [CommentarySnapshot(**item) for item in raw["commentary_snapshots"]]
            holdings = [HoldingsSnapshot(**item) for item in raw["holdings_snapshots"]]
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
                    commentary_snapshots=commentary,
                    holdings_snapshots=holdings,
                    blind_spots=list(raw["blind_spots"]),
                    debate_role=raw["debate_role"],
                )
            )
        if len(profiles) != 10:
            raise ValidationError(f"Expected 10 investor profiles, found {len(profiles)}")
        return profiles

    @cached_property
    def companies(self) -> dict[str, CompanyRecord]:
        companies: dict[str, CompanyRecord] = {}
        for path in sorted((self.data_dir / "fixtures" / "companies").glob("*.json")):
            raw = json.loads(path.read_text())
            companies[raw["ticker"].upper()] = self._company_from_raw(raw)
        return companies

    @cached_property
    def macro_record(self) -> MacroRecord:
        path = self.data_dir / "fixtures" / "macro" / "us_global.json"
        raw = json.loads(path.read_text())
        return MacroRecord(
            as_of=raw["as_of"],
            scope=raw["scope"],
            metrics=dict(raw["metrics"]),
            supplemental_metrics=dict(raw["supplemental_metrics"]),
            markets={name: dict(values) for name, values in raw["markets"].items()},
        )

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

    def ensure_company_fixture(self, question: str, context: str = "") -> CompanyRecord | None:
        combined = f"{question}\n{context}".strip()
        lowered = combined.lower()
        if not any(hint in lowered for hint in STOCK_PROMPT_HINTS):
            return None

        identifier = self._infer_company_identifier(combined)
        if identifier is None:
            return None

        ticker = identifier["ticker"]
        existing = self.companies.get(ticker)
        if existing is not None:
            return existing

        raw = self._build_placeholder_company_fixture(
            ticker=ticker,
            name=identifier["name"],
            combined_text=combined,
        )
        path = self.data_dir / "fixtures" / "companies" / f"{ticker.lower()}.json"
        path.write_text(json.dumps(raw, indent=2) + "\n")
        company = self._company_from_raw(raw)
        self.companies[ticker] = company
        return company

    def metric_value_for_company(self, company: CompanyRecord, metric: str) -> Any | None:
        stock = company.stock
        if metric in stock and stock.get(metric) is not None:
            return stock.get(metric)
        for section in ("operating_metrics", "valuation_metrics", "balance_sheet_metrics", "supplemental_metrics"):
            values = stock.get(section, {})
            if metric in values:
                return values[metric]
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

    def _company_from_raw(self, raw: dict[str, Any]) -> CompanyRecord:
        return CompanyRecord(
            ticker=raw["ticker"].upper(),
            name=raw["name"],
            aliases=[alias.lower() for alias in raw["aliases"]],
            is_public=bool(raw["is_public"]),
            is_tech=bool(raw["is_tech"]),
            sector=raw["sector"],
            industry=raw["industry"],
            archetype=raw["archetype"],
            description=raw["description"],
            technology=dict(raw["technology"]),
            stock=dict(raw["stock"]),
        )

    def _infer_company_identifier(self, text: str) -> dict[str, str] | None:
        ticker_match = None
        for token in UPPERCASE_TICKER_PATTERN.findall(text):
            if token not in TICKER_STOPWORDS:
                ticker_match = token
                break
        if ticker_match:
            return {"ticker": ticker_match, "name": ticker_match}

        company_match = COMPANY_NAME_PATTERN.search(text)
        if company_match:
            name = company_match.group(1).strip()
            ticker = re.sub(r"[^A-Za-z0-9]", "", name).upper()[:5] or "TBD"
            return {"ticker": ticker, "name": name.title()}
        return None

    def _build_placeholder_company_fixture(self, ticker: str, name: str, combined_text: str) -> dict[str, Any]:
        lowered = combined_text.lower()
        is_tech = any(
            term in lowered
            for term in (
                "tech",
                "technology",
                "software",
                "chip",
                "semiconductor",
                "ai",
                "cloud",
                "nuclear",
                "reactor",
                "smr",
                "microreactor",
            )
        )
        sector = "Industrials"
        industry = "Unclassified Public Company"
        archetype = "industrial_cyclical"
        if any(term in lowered for term in ("bank", "financial", "lender", "credit", "deposit")):
            sector = "Financials"
            industry = "Diversified Banks"
            archetype = "bank"
        elif any(term in lowered for term in ("nuclear", "reactor", "smr", "microreactor", "uranium")):
            sector = "Utilities"
            industry = "Advanced Nuclear Power"
            archetype = "developmental_energy_technology"
            is_tech = True
        elif any(term in lowered for term in ("energy", "utility", "power")):
            sector = "Energy"
            industry = "Energy Infrastructure"
            archetype = "energy_materials"
        elif is_tech:
            sector = "Technology"
            industry = "Software and Platform"
            archetype = "software_platform"

        return {
            "ticker": ticker,
            "name": name,
            "aliases": [ticker.lower(), name.lower()],
            "is_public": True,
            "is_tech": is_tech,
            "sector": sector,
            "industry": industry,
            "archetype": archetype,
            "description": f"Auto-created placeholder fixture for {name}. Replace this with a real company description and updated metrics.",
            "technology": {
                "summary": "Placeholder technology summary. Fill in the actual product, technology, or operating model.",
                "world_impact": "Placeholder impact assessment. Replace with the real market or societal impact.",
                "feasibility": "Unknown until real research is added.",
                "requirements": ["Research required", "Management and product review", "Real operating data"],
                "constraints": ["Metrics missing", "No live company data loaded yet"],
                "competitor_technologies": ["Unknown"],
                "preferred_technology": "Unknown",
                "preferred_rationale": "This fixture was auto-created from a stock-style prompt and needs manual enrichment.",
                "open_unknowns": ["Technology details and competitive positioning need to be added."]
            },
            "stock": {
                "as_of": "unknown",
                "currency": "USD",
                "price": None,
                "market_cap": None,
                "enterprise_value": None,
                "segment_mix": {},
                "operating_metrics": {},
                "valuation_metrics": {},
                "balance_sheet_metrics": {},
                "supplemental_metrics": {},
                "commentary": "This fixture was auto-created because the company was missing from the local fixture set."
            }
        }
