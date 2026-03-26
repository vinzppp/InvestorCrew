from __future__ import annotations

import argparse
from pathlib import Path

from investorcrew.service import InvestorCrewService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="investorcrew")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Analyze a question with InvestorCrew")
    ask_parser.add_argument("--question", required=True, help="Investment, technology, or macro question")
    ask_parser.add_argument("--context-file", help="Optional path to additional context")
    ask_parser.add_argument("--output-dir", help="Optional directory to write Markdown and JSON outputs")

    api_parser = subparsers.add_parser("api", help="Run the InvestorCrew FastAPI server")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)
    api_parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "api":
        try:
            import uvicorn
        except ModuleNotFoundError as exc:
            raise RuntimeError("uvicorn is required to run the API server. Install project dependencies first.") from exc
        uvicorn.run("investorcrew.api:create_app", host=args.host, port=args.port, reload=args.reload, factory=True)
        return 0

    context = ""
    if args.context_file:
        context = Path(args.context_file).read_text()

    service = InvestorCrewService()
    result = service.execute_run(
        question=args.question,
        context=context,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )

    markdown_path = result.saved_markdown_path or ""
    markdown_content = Path(markdown_path).read_text() if markdown_path else ""
    print(markdown_content, end="")
    print()
    print(f"Saved Markdown: {result.saved_markdown_path}")
    print(f"Saved JSON: {result.saved_json_path}")
    return 0
