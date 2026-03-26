import {
  CompanyDetail,
  CompanySummary,
  InvestorProfilePayload,
  PlanningDraft,
  PromptTemplate,
  ReportDetail,
  ReportEvent,
  RunRecord,
  SettingRecord
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_INVESTORCREW_API_BASE ?? "http://127.0.0.1:8000";

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export function getApiBase(): string {
  return API_BASE;
}

export function getReportArtifactUrl(reportId: string, artifactKind: "markdown" | "json"): string {
  return `${API_BASE}/api/reports/${reportId}/artifacts/${artifactKind}`;
}

export async function createPlan(question: string, context: string, researchMode?: string): Promise<PlanningDraft> {
  return readJson<PlanningDraft>("/api/plans", {
    method: "POST",
    body: JSON.stringify({ question, context, research_mode: researchMode ?? null })
  });
}

export async function getPlan(planId: string): Promise<PlanningDraft> {
  return readJson<PlanningDraft>(`/api/plans/${planId}`);
}

export async function updatePlan(planId: string, payload: Record<string, unknown>): Promise<PlanningDraft> {
  return readJson<PlanningDraft>(`/api/plans/${planId}`, {
    method: "PUT",
    body: JSON.stringify({ payload })
  });
}

export async function approvePlan(planId: string): Promise<RunRecord> {
  return readJson<RunRecord>(`/api/plans/${planId}/approve`, {
    method: "POST"
  });
}

export async function createRun(question: string, context: string): Promise<RunRecord> {
  return readJson<RunRecord>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ question, context })
  });
}

export async function getRun(runId: string): Promise<RunRecord> {
  return readJson<RunRecord>(`/api/runs/${runId}`);
}

export async function getRunEvents(runId: string): Promise<ReportEvent[]> {
  const payload = await readJson<{ items: ReportEvent[] }>(`/api/runs/${runId}/events`);
  return payload.items;
}

export async function listCompanies(search?: string): Promise<CompanySummary[]> {
  const suffix = search ? `?search=${encodeURIComponent(search)}` : "";
  const payload = await readJson<{ items: CompanySummary[] }>(`/api/companies${suffix}`);
  return payload.items;
}

export async function getCompany(companyId: string): Promise<CompanyDetail> {
  return readJson<CompanyDetail>(`/api/companies/${companyId}`);
}

export async function updateCompany(companyId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return readJson<Record<string, unknown>>(`/api/companies/${companyId}`, {
    method: "PUT",
    body: JSON.stringify({ payload })
  });
}

export async function getReport(reportId: string): Promise<ReportDetail> {
  return readJson<ReportDetail>(`/api/reports/${reportId}`);
}

export async function createSelfReview(reportId: string): Promise<Record<string, unknown>> {
  return readJson<Record<string, unknown>>(`/api/reports/${reportId}/self-review`, {
    method: "POST"
  });
}

export async function listPrompts(): Promise<PromptTemplate[]> {
  const payload = await readJson<{ items: PromptTemplate[] }>("/api/config/prompts");
  return payload.items;
}

export async function updatePrompt(
  promptId: string,
  content: string,
  label?: string,
  description?: string
): Promise<Record<string, unknown>> {
  return readJson<Record<string, unknown>>(`/api/config/prompts/${promptId}`, {
    method: "PUT",
    body: JSON.stringify({ content, label, description })
  });
}

export async function listInvestors(): Promise<InvestorProfilePayload[]> {
  const payload = await readJson<{ items: InvestorProfilePayload[] }>("/api/config/investors");
  return payload.items;
}

export async function updateInvestor(slug: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return readJson<Record<string, unknown>>(`/api/config/investors/${slug}`, {
    method: "PUT",
    body: JSON.stringify({ payload })
  });
}

export async function listSettings(): Promise<SettingRecord[]> {
  const payload = await readJson<{ items: SettingRecord[] }>("/api/config/settings");
  return payload.items;
}

export async function updateSetting(key: string, value: unknown): Promise<Record<string, unknown>> {
  return readJson<Record<string, unknown>>(`/api/config/settings/${key}`, {
    method: "PUT",
    body: JSON.stringify({ value })
  });
}
