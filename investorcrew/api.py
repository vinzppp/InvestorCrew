from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from investorcrew.service import InvestorCrewService


class RunCreateRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: str = ""


class PromptUpdateRequest(BaseModel):
    content: str
    label: str | None = None
    description: str | None = None


class InvestorUpdateRequest(BaseModel):
    payload: dict[str, Any]


class SettingUpdateRequest(BaseModel):
    value: Any


class CompanyUpdateRequest(BaseModel):
    payload: dict[str, Any]


def create_app() -> FastAPI:
    app = FastAPI(title="InvestorCrew API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = InvestorCrewService()

    def _run_in_background(run_id: str, question: str, context: str) -> None:
        def worker() -> None:
            service.execute_run(question=question, context=context, run_id=run_id)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/runs")
    def create_run(request: RunCreateRequest) -> dict[str, Any]:
        run_id = service.create_run(question=request.question, context=request.context)
        _run_in_background(run_id, request.question, request.context)
        return service.get_run(run_id)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return service.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/runs/{run_id}/events")
    def get_run_events(run_id: str) -> dict[str, Any]:
        try:
            return {"items": service.get_run_events(run_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/companies")
    def list_companies(search: str | None = Query(default=None)) -> dict[str, Any]:
        return {"items": service.list_companies(search=search)}

    @app.get("/api/companies/{company_id}")
    def get_company(company_id: str) -> dict[str, Any]:
        try:
            return service.get_company_detail(company_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/companies/{company_id}")
    def update_company(company_id: str, request: CompanyUpdateRequest) -> dict[str, Any]:
        try:
            return service.update_company(company_id, request.payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/companies/{company_id}/reports")
    def get_company_reports(company_id: str) -> dict[str, Any]:
        return {"items": service.list_company_reports(company_id)}

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        try:
            return service.get_report_detail(report_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/reports/{report_id}/artifacts/{artifact_kind}")
    def get_report_artifact(report_id: str, artifact_kind: str) -> FileResponse:
        try:
            run = service.get_run(report_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if artifact_kind == "markdown":
            path_value = run.get("markdown_path")
            media_type = "text/markdown"
            filename = "investorcrew_report.md"
        elif artifact_kind == "json":
            path_value = run.get("json_path")
            media_type = "application/json"
            filename = "investorcrew_report.json"
        else:
            raise HTTPException(status_code=404, detail=f"Unknown artifact kind: {artifact_kind}")

        if not path_value:
            raise HTTPException(status_code=404, detail=f"{artifact_kind} artifact is not available")

        path = Path(path_value)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{artifact_kind} artifact file is missing")

        return FileResponse(path=path, media_type=media_type, filename=filename)

    @app.post("/api/reports/{report_id}/self-review")
    def create_self_review(report_id: str) -> dict[str, Any]:
        try:
            return service.generate_self_review(report_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/config/investors")
    def list_investors() -> dict[str, Any]:
        return {"items": service.list_investors()}

    @app.put("/api/config/investors/{investor_id}")
    def update_investor(investor_id: str, request: InvestorUpdateRequest) -> dict[str, Any]:
        try:
            return service.update_investor(investor_id, request.payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/config/prompts")
    def list_prompts() -> dict[str, Any]:
        return {"items": service.list_prompts()}

    @app.put("/api/config/prompts/{prompt_id}")
    def update_prompt(prompt_id: str, request: PromptUpdateRequest) -> dict[str, Any]:
        try:
            return service.update_prompt(
                key=prompt_id,
                content=request.content,
                label=request.label,
                description=request.description,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/config/settings")
    def list_settings() -> dict[str, Any]:
        return {"items": service.list_settings()}

    @app.put("/api/config/settings/{setting_id}")
    def update_setting(setting_id: str, request: SettingUpdateRequest) -> dict[str, Any]:
        return service.update_setting(setting_id, request.value)

    return app
