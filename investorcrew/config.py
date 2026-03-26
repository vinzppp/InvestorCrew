from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


@dataclass(slots=True)
class AppConfig:
    data_dir: Path
    db_path: Path
    outputs_dir: Path
    llm_provider: str
    llm_model: str
    openai_api_key: str | None
    openai_base_url: str
    market_data_provider: str
    macro_data_provider: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        data_dir = Path(os.getenv("INVESTORCREW_DATA_DIR", str(default_data_dir())))
        return cls(
            data_dir=data_dir,
            db_path=Path(os.getenv("INVESTORCREW_DB_PATH", str(data_dir / "investorcrew.db"))),
            outputs_dir=Path(os.getenv("INVESTORCREW_OUTPUTS_DIR", str(default_data_dir().parent / "outputs"))),
            llm_provider=os.getenv("INVESTORCREW_LLM_PROVIDER", "heuristic"),
            llm_model=os.getenv("INVESTORCREW_LLM_MODEL", "gpt-5.4-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            market_data_provider=os.getenv("INVESTORCREW_MARKET_DATA_PROVIDER", "fixture"),
            macro_data_provider=os.getenv("INVESTORCREW_MACRO_DATA_PROVIDER", "fixture"),
        )
