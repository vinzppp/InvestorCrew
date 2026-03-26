export type RunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

export interface CompanySummary {
  id: string;
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  archetype: string;
  is_tech: boolean;
  report_count: number;
  last_report_at: string | null;
}

export interface CompanyRecordPayload {
  ticker: string;
  name: string;
  aliases: string[];
  is_public: boolean;
  is_tech: boolean;
  sector: string;
  industry: string;
  archetype: string;
  description: string;
  technology: Record<string, unknown>;
  stock: Record<string, unknown>;
}

export interface ReportSummary {
  id: string;
  question: string;
  status: RunStatus;
  company_ticker: string | null;
  company_name: string | null;
  created_at: string;
  completed_at: string | null;
  markdown_path: string | null;
  json_path: string | null;
}

export interface PromptTemplate {
  key: string;
  label: string;
  description: string;
  content: string;
  created_at?: string;
  updated_at?: string;
}

export interface SettingRecord {
  key: string;
  value: unknown;
}

export interface ReportEvent {
  sequence: number;
  stage: string;
  event_type: string;
  actor: string | null;
  title: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RunRecord {
  id: string;
  question: string;
  context: string;
  company_ticker: string | null;
  company_name: string | null;
  status: RunStatus;
  classification: Record<string, unknown> | null;
  final_result: Record<string, unknown> | null;
  prompt_snapshot: Record<string, string>;
  markdown_path: string | null;
  json_path: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface CompanyDetail {
  company: CompanyRecordPayload;
  reports: ReportSummary[];
}

export interface SelfReviewRecord {
  review_id: string;
  run_id: string;
  summary: string;
  recommendations: Array<{
    category: string;
    priority: string;
    recommendation: string;
    rationale: string;
  }>;
  created_at: string;
}

export interface ReportDetail {
  run: RunRecord;
  events: ReportEvent[];
  artifacts: Array<{
    artifact_type: string;
    title: string;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
  proposals: Array<Record<string, unknown>>;
  votes: Array<Record<string, unknown>>;
  self_reviews: SelfReviewRecord[];
  markdown_content: string | null;
}

export interface InvestorProfilePayload {
  slug: string;
  name: string;
  style_tags: string[];
  philosophy: string;
  preferred_metrics: string[];
  heuristics: string[];
  risk_rules: string[];
  portfolio_habits: string[];
  commentary_snapshots: Array<Record<string, unknown>>;
  holdings_snapshots: Array<Record<string, unknown>>;
  blind_spots: string[];
  debate_role: string;
}
