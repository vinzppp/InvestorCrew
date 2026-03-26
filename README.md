# InvestorCrew

InvestorCrew is a local-first investment research system with:

- a Python 3.12 CLI,
- a FastAPI backend with SQLite persistence,
- a Next.js web app with `Ask`, `Library`, and `Configure` tabs.

Each run routes a question through pre-debate diligence, captures the full transcript of the crew discussion, saves Markdown/JSON artifacts, and stores everything in a local database for later review.

## Features

- Classifies questions into technology, stock, macro, or mixed.
- Selects metrics before building reports, so valuation and macro analysis fit the subject.
- Generates technical, stock, and economic diligence packets.
- Runs a non-voting moderator plus 10 investor personas.
- Supports up to 2 diligence follow-up rounds.
- Persists companies, reports, transcript events, proposals, votes, settings, prompts, and self-reviews in SQLite.
- Produces both Markdown and JSON exports for each run.
- Includes an on-demand self-review workflow for completed reports.

## CLI Quick Start

```bash
python3 -m investorcrew ask --question "Should I buy NVIDIA given AI spending and the current macro backdrop?"
```

You can optionally provide extra context:

```bash
python3 -m investorcrew ask --question "How should I think about JPMorgan here?" --context-file notes.txt
```

If you do not pass `--output-dir`, InvestorCrew saves automatically under `outputs/<ticker-or-question-slug>/<timestamp>/` and prints the Markdown and JSON paths after the memo.

## Run The API

Start the FastAPI server from the repo root:

```bash
python3 -m investorcrew api --host 127.0.0.1 --port 8000
```

Main endpoints:

- `POST /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/events`
- `GET /api/companies`
- `GET /api/companies/{ticker}`
- `GET /api/companies/{ticker}/reports`
- `GET /api/reports/{id}`
- `POST /api/reports/{id}/self-review`
- `GET /api/config/investors`
- `GET /api/config/prompts`
- `GET /api/config/settings`

The API also exposes saved report downloads:

- `GET /api/reports/{id}/artifacts/markdown`
- `GET /api/reports/{id}/artifacts/json`

## Run The Web App

Install web dependencies once:

```bash
cd web
npm install
```

Start the Next.js app:

```bash
cd web
npm run dev
```

By default the UI talks to `http://127.0.0.1:8000`. Override it with:

```bash
NEXT_PUBLIC_INVESTORCREW_API_BASE=http://127.0.0.1:8000
```

## Persistence

- SQLite database: `data/investorcrew.db` by default
- Saved report exports: `outputs/`
- Seed investor/company data: `data/investors/` and `data/fixtures/companies/`

On startup, the SQLite store bootstraps itself from the current fixture files and imports any existing saved output reports.

## Environment Variables

- `INVESTORCREW_DATA_DIR`: Override the default `data/` directory.
- `INVESTORCREW_DB_PATH`: Override the SQLite database path.
- `INVESTORCREW_OUTPUTS_DIR`: Override the report export directory.
- `INVESTORCREW_LLM_PROVIDER`: `heuristic` (default) or `openai`.
- `INVESTORCREW_LLM_MODEL`: Model name when using the OpenAI provider.
- `OPENAI_API_KEY`: Required when `INVESTORCREW_LLM_PROVIDER=openai`.
- `OPENAI_BASE_URL`: Optional override for the OpenAI API base URL.
- `INVESTORCREW_MARKET_DATA_PROVIDER`: `fixture` (default).
- `INVESTORCREW_MACRO_DATA_PROVIDER`: `fixture` (default).

## Notes

- Investor knowledge is curated and static in `data/investors/`.
- Stock and macro reports default to deterministic fixtures so the repo works offline and in tests.
- If you ask about a stock that is not in the local fixture set, InvestorCrew scaffolds a placeholder fixture under `data/fixtures/companies/` and continues the workflow.
- If a metric is unavailable, the system marks it missing instead of inventing it.

## Verification

Python test suite:

```bash
python3 -m unittest discover -s tests -v
```

Web typecheck:

```bash
cd web
npm run typecheck
```

Production web build:

```bash
cd web
npm run build
```
