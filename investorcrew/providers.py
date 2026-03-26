from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from typing import Any, Iterable

from investorcrew.config import AppConfig
from investorcrew.data_store import KnowledgeBase
from investorcrew.models import CompanyRecord, MacroRecord, PlanningSource


class LLMClient(ABC):
    @abstractmethod
    def summarize(self, topic: str, bullets: Iterable[str]) -> str:
        raise NotImplementedError


class HeuristicLLMClient(LLMClient):
    def summarize(self, topic: str, bullets: Iterable[str]) -> str:
        cleaned = [bullet.strip().rstrip(".") for bullet in bullets if bullet.strip()]
        if not cleaned:
            return f"{topic} remains under review with limited evidence."
        return f"{topic}: " + "; ".join(cleaned[:4]) + "."


class OpenAIResponsesLLMClient(LLMClient):
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def summarize(self, topic: str, bullets: Iterable[str]) -> str:
        prompt = "\n".join(f"- {bullet}" for bullet in bullets if bullet.strip())
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": "You are a concise investment research assistant. Write one short paragraph.",
                },
                {
                    "role": "user",
                    "content": f"Summarize this topic in 3-4 sentences.\nTopic: {topic}\nSignals:\n{prompt}",
                },
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc
        if "output_text" in data and data["output_text"]:
            return data["output_text"].strip()
        outputs = data.get("output", [])
        for item in outputs:
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return str(content["text"]).strip()
        raise RuntimeError("OpenAI response did not include output text")


class MarketDataClient(ABC):
    @abstractmethod
    def lookup_company(self, identifier: str) -> CompanyRecord | None:
        raise NotImplementedError

    @abstractmethod
    def get_supplemental_metrics(self, company: CompanyRecord, metrics: list[str]) -> dict[str, Any]:
        raise NotImplementedError


class MacroDataClient(ABC):
    @abstractmethod
    def get_overview(self) -> MacroRecord:
        raise NotImplementedError

    @abstractmethod
    def get_supplemental_metrics(self, metrics: list[str]) -> dict[str, Any]:
        raise NotImplementedError


class ResearchClient(ABC):
    @abstractmethod
    def collect_sources(
        self,
        question: str,
        context: str,
        company: CompanyRecord | None,
        mode: str,
    ) -> tuple[str, list[PlanningSource]]:
        raise NotImplementedError


class FixtureMarketDataClient(MarketDataClient):
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    def lookup_company(self, identifier: str) -> CompanyRecord | None:
        company = self.knowledge_base.companies.get(identifier.upper())
        if company is not None:
            return company
        return self.knowledge_base.find_company(identifier)

    def get_supplemental_metrics(self, company: CompanyRecord, metrics: list[str]) -> dict[str, Any]:
        supplemental = company.stock.get("supplemental_metrics", {})
        return {metric: supplemental[metric] for metric in metrics if metric in supplemental}


class FixtureMacroDataClient(MacroDataClient):
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    def get_overview(self) -> MacroRecord:
        return self.knowledge_base.macro_record

    def get_supplemental_metrics(self, metrics: list[str]) -> dict[str, Any]:
        supplemental = self.knowledge_base.macro_record.supplemental_metrics
        return {metric: supplemental[metric] for metric in metrics if metric in supplemental}


class FixtureResearchClient(ResearchClient):
    def collect_sources(
        self,
        question: str,
        context: str,
        company: CompanyRecord | None,
        mode: str,
    ) -> tuple[str, list[PlanningSource]]:
        sources: list[PlanningSource] = []

        if company:
            sources.extend(self._company_sources(company))

        context_sources = self._context_sources(context)
        sources.extend(context_sources)

        deduped: list[PlanningSource] = []
        seen: set[tuple[str, str, str]] = set()
        for source in sources:
            key = (source.title, source.url, source.bucket)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)

        if context_sources and any(source.source_kind == "core" for source in deduped):
            return "local_only", deduped
        if context_sources:
            return "user_context_only", deduped
        return "local_only", deduped

    def _company_sources(self, company: CompanyRecord) -> list[PlanningSource]:
        sources: list[PlanningSource] = []
        official_site = self._infer_official_site(company)
        ir_base = official_site.rstrip("/") if official_site else ""
        filings_url = f"https://www.sec.gov/edgar/search/#/q={company.ticker}"
        published_at = str(company.stock.get("as_of")) if company.stock.get("as_of") else None

        core_templates = [
            (
                "sec_filings",
                "core",
                f"{company.name} SEC filing search",
                filings_url,
                "SEC EDGAR",
                "Use filings to anchor revenue model, risk factors, capital needs, dilution, and governance.",
            ),
            (
                "sec_filings",
                "core",
                f"{company.name} annual report / 10-K",
                filings_url,
                "SEC EDGAR",
                "Annual report coverage should define the business model, strategy, major risks, and long-term capital plan.",
            ),
            (
                "sec_filings",
                "core",
                f"{company.name} quarterly report / 10-Q",
                filings_url,
                "SEC EDGAR",
                "Quarterly filings should be used to track liquidity, updated milestones, customer concentration, and recent operating shifts.",
            ),
            (
                "sec_filings",
                "core",
                f"{company.name} proxy / governance filing",
                filings_url,
                "SEC EDGAR",
                "Proxy materials help diligence leadership incentives, ownership, related-party risk, and shareholder alignment.",
            ),
            (
                "investor_relations",
                "core",
                f"{company.name} investor relations overview",
                f"{ir_base}/investors" if ir_base else "",
                company.name,
                "Investor relations should provide the current company story, milestones, and investor presentation library.",
            ),
            (
                "investor_relations",
                "core",
                f"{company.name} investor presentation",
                f"{ir_base}/investors" if ir_base else "",
                company.name,
                "Investor decks are useful for strategy framing, product positioning, customer case studies, and capital priorities.",
            ),
            (
                "investor_relations",
                "core",
                f"{company.name} press releases",
                f"{ir_base}/news" if ir_base else "",
                company.name,
                "Press releases should be scanned for partnerships, launches, financing updates, regulatory milestones, and customer wins.",
            ),
            (
                "company_website",
                "core",
                f"{company.name} products and technology",
                official_site,
                company.name,
                "Company pages should explain the product line, technical approach, and where the company claims product differentiation.",
            ),
            (
                "company_website",
                "core",
                f"{company.name} strategy and mission",
                official_site,
                company.name,
                "Strategy pages should clarify the market problem, company priorities, and what management thinks matters most.",
            ),
            (
                "company_website",
                "core",
                f"{company.name} leadership team",
                f"{ir_base}/about" if ir_base else official_site,
                company.name,
                "Leadership pages help build the management and technical credibility picture.",
            ),
            (
                "company_website",
                "core",
                f"{company.name} customers, partners, and deployments",
                official_site,
                company.name,
                "Customer, partner, and deployment pages help test whether the product has real commercial pull.",
            ),
            (
                "transcripts",
                "core",
                f"{company.name} earnings call transcript",
                f"https://www.youtube.com/results?search_query={company.name.replace(' ', '+')}+earnings+call",
                "Transcript target",
                "Earnings transcripts should be used to capture management commentary on demand, strategy, risk, and near-term milestones.",
            ),
            (
                "transcripts",
                "core",
                f"{company.name} conference appearance transcript",
                f"https://www.youtube.com/results?search_query={company.name.replace(' ', '+')}+conference+interview",
                "Transcript target",
                "Conference transcripts often surface competitive positioning, customer demand, and capital-markets messaging.",
            ),
            (
                "transcripts",
                "core",
                f"{company.name} founder or leadership interview transcript",
                f"https://www.youtube.com/results?search_query={company.name.replace(' ', '+')}+CEO+interview",
                "Transcript target",
                "Founder and leadership interviews are useful for conviction, technical depth, and how honestly management frames risk.",
            ),
            (
                "transcripts",
                "core",
                f"{company.name} podcast transcript",
                f"https://www.youtube.com/results?search_query={company.name.replace(' ', '+')}+podcast",
                "Transcript target",
                "Podcast transcripts can help diligence culture, strategic intent, product roadmap, and what management chooses to emphasize.",
            ),
            (
                "industry_research",
                "core",
                f"{company.industry} market sizing research",
                "",
                "Industry research target",
                "Industry sizing sources should estimate TAM, growth rate, adoption drivers, and what demand assumptions the thesis requires.",
            ),
            (
                "industry_research",
                "core",
                f"{company.industry} competitive landscape",
                "",
                "Industry research target",
                "Competitive research should map incumbents, substitutes, customer switching costs, and where margins could compress.",
            ),
            (
                "industry_research",
                "core",
                f"{company.industry} customer demand and risk drivers",
                "",
                "Industry research target",
                "Industry demand sources should explain who buys the product, why they buy, and what macro or regulatory factors could hurt demand.",
            ),
        ]

        for bucket, source_kind, title, url, publisher, snippet in core_templates:
            sources.append(
                PlanningSource(
                    title=title,
                    url=url,
                    publisher=publisher,
                    published_at=published_at,
                    snippet=snippet,
                    bucket=bucket,
                    source_kind=source_kind,
                )
            )

        tech_sources = company.technology.get("sources", [])
        stock_sources = company.stock.get("sources", [])
        for raw in [*tech_sources, *stock_sources]:
            if not isinstance(raw, dict):
                continue
            publisher = str(raw.get("publisher", "Fixture"))
            bucket = self._bucket_for_source(publisher, str(raw.get("url", "")))
            source_kind = "reference" if bucket == "listing_reference" else "core"
            sources.append(
                PlanningSource(
                    title=str(raw.get("title", company.name)),
                    url=str(raw.get("url", "")),
                    publisher=publisher,
                    published_at=str(raw.get("published_at")) if raw.get("published_at") else published_at,
                    snippet=str(raw.get("snippet", raw.get("note", "Fixture research note"))),
                    bucket=bucket,
                    source_kind=source_kind,
                )
            )

        commentary = str(company.stock.get("commentary", "")).strip()
        if commentary:
            for publisher, url in (
                ("Robinhood", f"https://robinhood.com/us/en/stocks/{company.ticker}/"),
                ("Yahoo Finance", f"https://finance.yahoo.com/quote/{company.ticker}/"),
                ("MarketWatch", f"https://www.marketwatch.com/investing/stock/{company.ticker.lower()}"),
            ):
                sources.append(
                    PlanningSource(
                        title=f"{company.name} listing reference on {publisher}",
                        url=url,
                        publisher=publisher,
                        published_at=published_at,
                        snippet="Use only to confirm listing status and basic market reference data, not as core diligence evidence.",
                        bucket="listing_reference",
                        source_kind="reference",
                    )
                )
        return sources

    def _context_sources(self, context: str) -> list[PlanningSource]:
        sources: list[PlanningSource] = []
        for line in [item.strip() for item in context.splitlines() if item.strip()]:
            if line.startswith("http://") or line.startswith("https://"):
                publisher = line.split("/")[2]
                sources.append(
                    PlanningSource(
                        title=f"User-provided source from {publisher}",
                        url=line,
                        publisher=publisher,
                        published_at=None,
                        snippet="User provided this source in context.",
                        bucket="user_context",
                        source_kind="core",
                    )
                )
        return sources

    def _infer_official_site(self, company: CompanyRecord) -> str:
        raw_sources = [*company.technology.get("sources", []), *company.stock.get("sources", [])]
        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url", "")).strip()
            publisher = str(raw.get("publisher", "")).strip().lower()
            if not url:
                continue
            if any(token in publisher for token in (company.name.lower(), company.ticker.lower())):
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    return f"{parsed.scheme}://{parsed.netloc}"
            if any(token in url.lower() for token in ("yahoo.com", "marketwatch.com", "robinhood.com")):
                continue
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return ""

    def _bucket_for_source(self, publisher: str, url: str) -> str:
        lowered = f"{publisher} {url}".lower()
        if any(domain in lowered for domain in ("robinhood", "yahoo", "marketwatch")):
            return "listing_reference"
        if "sec" in lowered or "edgar" in lowered:
            return "sec_filings"
        if any(token in lowered for token in ("investor", "presentation", "press release", "news")):
            return "investor_relations"
        if any(token in lowered for token in ("youtube", "transcript", "podcast", "conference", "interview", "earnings call")):
            return "transcripts"
        if any(token in lowered for token in ("market size", "industry", "competitive")):
            return "industry_research"
        return "company_website"


def build_llm_client(config: AppConfig) -> LLMClient:
    if config.llm_provider == "heuristic":
        return HeuristicLLMClient()
    if config.llm_provider == "openai":
        if not config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when INVESTORCREW_LLM_PROVIDER=openai")
        return OpenAIResponsesLLMClient(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.llm_model,
        )
    raise RuntimeError(f"Unsupported LLM provider: {config.llm_provider}")


def build_market_data_client(config: AppConfig, knowledge_base: KnowledgeBase) -> MarketDataClient:
    if config.market_data_provider == "fixture":
        return FixtureMarketDataClient(knowledge_base)
    raise RuntimeError(f"Unsupported market data provider: {config.market_data_provider}")


def build_macro_data_client(config: AppConfig, knowledge_base: KnowledgeBase) -> MacroDataClient:
    if config.macro_data_provider == "fixture":
        return FixtureMacroDataClient(knowledge_base)
    raise RuntimeError(f"Unsupported macro data provider: {config.macro_data_provider}")


def build_research_client(config: AppConfig, knowledge_base: KnowledgeBase) -> ResearchClient:
    return FixtureResearchClient()
