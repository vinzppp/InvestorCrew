from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Iterable

from investorcrew.config import AppConfig
from investorcrew.data_store import KnowledgeBase
from investorcrew.models import CompanyRecord, MacroRecord


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
