from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from investorcrew.models import RunResult


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "run"


def build_report_output_dir(outputs_dir: Path, result: RunResult) -> Path:
    company_stem = result.classification.company_ticker.lower() if result.classification.company_ticker else _slugify(result.question)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return outputs_dir / company_stem / timestamp


def save_run_artifacts(
    result: RunResult,
    markdown: str,
    json_output: str,
    outputs_dir: Path,
    explicit_output_dir: Path | None = None,
) -> tuple[Path, Path]:
    target_dir = explicit_output_dir if explicit_output_dir else build_report_output_dir(outputs_dir, result)
    target_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = (target_dir / "investorcrew_report.md").resolve()
    json_path = (target_dir / "investorcrew_report.json").resolve()
    markdown_path.write_text(markdown)
    json_path.write_text(json_output)
    return markdown_path, json_path
