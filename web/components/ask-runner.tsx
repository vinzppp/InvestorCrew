"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { approvePlan, createPlan, getRun, updatePlan } from "@/lib/api";
import { PlanningDraft, RunRecord } from "@/lib/types";

function statusTone(status: string): string {
  if (status === "COMPLETED") return "good";
  if (status === "FAILED") return "bad";
  if (status === "RUNNING") return "warn";
  return "neutral";
}

function promptOrder(promptPack: Record<string, string>): string[] {
  const preferred = [
    "technical_due_diligence",
    "stock_due_diligence",
    "industry_due_diligence",
    "economic_overview",
    "technical_reviewer",
    "investor_analysis",
    "investment_committee"
  ];
  return preferred.filter((key) => key in promptPack);
}

function prettyLabel(stage: string): string {
  return stage
    .split("_")
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(" ");
}

function promptHelper(key: string): string {
  const copy: Record<string, string> = {
    technical_due_diligence: "How the technical team should reason, what it must prove, and what depth counts as acceptable.",
    stock_due_diligence: "How the stock team should choose metrics, frame valuation, and stress-test financing or cash flow.",
    industry_due_diligence: "How the industry team should size the market, map competitors, and identify structural opportunities and risks.",
    economic_overview: "How the macro team should frame the regime, compare markets, and isolate what actually changes the decision.",
    technical_reviewer: "How the technical reviewer should decide whether the work is deep and source-backed enough to proceed.",
    investor_analysis: "How the investors should weigh fit, edge, upside, falsification, and whether to support, oppose, or pass.",
    investment_committee: "How the committee should synthesize thesis, opportunities, risks, and tradeoffs into the final disposition and proposals."
  };
  return copy[key] ?? "How this handoff prompt should guide the next team.";
}

export function AskRunner() {
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [plan, setPlan] = useState<PlanningDraft | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planningBusy, setPlanningBusy] = useState(false);
  const [approveBusy, setApproveBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const pollingRef = useRef<number | null>(null);

  const reportHref = useMemo(() => {
    if (!run?.company_ticker) return null;
    return `/library/${run.company_ticker}/reports/${run.id}`;
  }, [run]);
  const planClassification = (plan?.classification ?? {}) as Record<string, unknown>;

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
      }
    };
  }, []);

  async function refresh(runId: string) {
    const nextRun = await getRun(runId);
    setRun(nextRun);
    if (nextRun.status === "COMPLETED" || nextRun.status === "FAILED") {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }
  }

  async function handleGeneratePlan(event: React.FormEvent) {
    event.preventDefault();
    setPlanningBusy(true);
    setError(null);
    setRun(null);
    try {
      const created = await createPlan(question, context);
      setPlan(created);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to generate plan");
    } finally {
      setPlanningBusy(false);
    }
  }

  async function savePlanDraft(): Promise<PlanningDraft | null> {
    if (!plan) return null;
    setSaveBusy(true);
    setError(null);
    try {
      const saved = await updatePlan(plan.plan_id, {
        asset_overview: plan.asset_overview,
        primary_strategy: plan.primary_strategy,
        secondary_strategies: plan.secondary_strategies,
        strategy_rationale: plan.strategy_rationale,
        key_study_questions: plan.key_study_questions,
        prompt_pack: plan.prompt_pack,
        approval_warning: plan.approval_warning
      });
      setPlan(saved);
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to save plan");
      return null;
    } finally {
      setSaveBusy(false);
    }
  }

  async function handleApprovePlan() {
    if (!plan) return;
    setApproveBusy(true);
    setError(null);
    try {
      const saved = await savePlanDraft();
      if (!saved) return;
      const createdRun = await approvePlan(saved.plan_id);
      setRun(createdRun);
      await refresh(createdRun.id);
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
      }
      pollingRef.current = window.setInterval(() => {
        void refresh(createdRun.id);
      }, 1500);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to approve plan");
    } finally {
      setApproveBusy(false);
    }
  }

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Ask Workflow</p>
            <h2>Plan first, then run the crew</h2>
            <p className="hero-copy">
              InvestorCrew now drafts the evaluation strategy before the chain starts. Review the asset overview,
              strategy, and tailored prompts first, then approve the run.
            </p>
          </div>
          {run && <span className={`status-pill ${statusTone(run.status)}`}>{run.status}</span>}
        </div>

        <form className="stack" onSubmit={handleGeneratePlan}>
          <div className="step-row">
            <span className="step-chip active">1. Draft plan</span>
            <span className={`step-chip ${plan ? "active" : ""}`}>2. Review prompts</span>
            <span className={`step-chip ${run ? "active" : ""}`}>3. Run debate</span>
          </div>
          <label className="field">
            <span>Question</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What do you think about investing in OKLO stock?"
              rows={4}
              required
            />
          </label>
          <label className="field">
            <span>Optional Context</span>
            <textarea
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="Paste notes, links, or background context for the crew."
              rows={6}
            />
          </label>
          <div className="actions">
            <button className="button primary" type="submit" disabled={planningBusy}>
              {planningBusy ? "Drafting Plan..." : "Generate Evaluation Plan"}
            </button>
            {reportHref && run?.status === "COMPLETED" && (
              <Link className="button subtle" href={reportHref}>
                Open Report
              </Link>
            )}
          </div>
          {error && <p className="error-text">{error}</p>}
        </form>
      </section>

      {plan && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Planning Draft</p>
              <h2>Review the tailored strategy before approval</h2>
              <p className="hero-copy">
                This plan decides what kind of bet the asset is, which questions matter most, and how the downstream
                teams should work.
              </p>
            </div>
            <span className="status-pill neutral">{plan.research_mode}</span>
          </div>

          <div className="section-grid">
            <article className="summary-card">
              <span className="meta-label">Routing</span>
              <strong>{String(planClassification["category"] ?? "n/a")}</strong>
              <p>{String(planClassification["reason"] ?? "")}</p>
            </article>
            <article className="summary-card">
              <span className="meta-label">Primary Strategy</span>
              <strong>{plan.primary_strategy}</strong>
              <p>{plan.strategy_rationale}</p>
            </article>
            <article className="summary-card">
              <span className="meta-label">Secondary Strategies</span>
              <p>{plan.secondary_strategies.length ? plan.secondary_strategies.join(", ") : "None"}</p>
            </article>
            <article className="summary-card">
              <span className="meta-label">Sources</span>
              <strong>{plan.source_count}</strong>
              <p>{plan.source_count >= 15 ? "Source coverage meets the planning target." : "Planning is still short of the 15-source target."}</p>
            </article>
          </div>

          {plan.approval_warning && <p className="warning-banner">{plan.approval_warning}</p>}

          <div className="stack">
            <label className="field">
              <span>Asset Overview</span>
              <textarea
                className="plan-textarea"
                value={plan.asset_overview}
                onChange={(event) => setPlan({ ...plan, asset_overview: event.target.value })}
                rows={6}
              />
            </label>

            <div className="section-grid">
              <article className="summary-card">
                <span className="meta-label">Listing Confirmation</span>
                <div className="analysis-box">{plan.listing_confirmation}</div>
              </article>
              <article className="summary-card">
                <span className="meta-label">Source Coverage</span>
                <div className="analysis-box">
                  {Object.entries(plan.source_buckets)
                    .map(([bucket, count]) => `${prettyLabel(bucket)}: ${count}`)
                    .join("\n") || "No source buckets yet."}
                </div>
              </article>
              <article className="summary-card">
                <span className="meta-label">Coverage Gaps</span>
                <div className="analysis-box">
                  {plan.coverage_gaps.length
                    ? plan.coverage_gaps.map((item) => `• ${prettyLabel(item)}`).join("\n")
                    : "No major coverage gaps flagged in the current plan."}
                </div>
              </article>
              <article className="summary-card">
                <span className="meta-label">What Kind of Bet?</span>
                <div className="analysis-box">
                  Primary: {plan.primary_strategy}
                  {"\n"}
                  Secondary: {plan.secondary_strategies.length ? plan.secondary_strategies.join(", ") : "None"}
                </div>
              </article>
            </div>

            <div className="split-fields">
              <label className="field">
                <span>Primary Strategy</span>
                <input
                  value={plan.primary_strategy}
                  onChange={(event) => setPlan({ ...plan, primary_strategy: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Secondary Strategies</span>
                <input
                  value={plan.secondary_strategies.join(", ")}
                  onChange={(event) =>
                    setPlan({
                      ...plan,
                      secondary_strategies: event.target.value
                        .split(",")
                        .map((item) => item.trim())
                        .filter(Boolean)
                    })
                  }
                />
              </label>
            </div>

            <label className="field">
              <span>Strategy Rationale</span>
              <textarea
                className="plan-textarea"
                value={plan.strategy_rationale}
                onChange={(event) => setPlan({ ...plan, strategy_rationale: event.target.value })}
                rows={5}
              />
            </label>

            <div className="card-grid">
              {[
                ["Industry Snapshot", plan.industry_summary],
                ["Leadership", plan.leadership_summary],
                ["Shareholders", plan.shareholder_summary],
                ["Strategy", plan.strategy_summary],
                ["Products And Technology", plan.product_summary],
                ["Customers And Go-To-Market", plan.customer_summary],
                ["Competitive Landscape", plan.competitive_landscape_summary]
              ].map(([title, value]) => (
                <article key={title} className="summary-card">
                  <span className="meta-label">{title}</span>
                  <div className="analysis-box analysis-box-tall">{value}</div>
                </article>
              ))}
            </div>

            <label className="field">
              <span>Key Study Questions</span>
              <textarea
                className="plan-textarea"
                value={plan.key_study_questions.join("\n")}
                onChange={(event) =>
                  setPlan({
                    ...plan,
                    key_study_questions: event.target.value
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean)
                  })
                }
                rows={8}
              />
            </label>

            <div className="stack">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Prompt Pack</p>
                  <h2>Editable downstream instructions</h2>
                </div>
              </div>
              <div className="stack">
                {promptOrder(plan.prompt_pack).map((key) => (
                  <label key={key} className="field">
                    <span>{prettyLabel(key)}</span>
                    <textarea
                      className="prompt-editor-large"
                      value={plan.prompt_pack[key]}
                      onChange={(event) =>
                        setPlan({
                          ...plan,
                          prompt_pack: {
                            ...plan.prompt_pack,
                            [key]: event.target.value
                          }
                        })
                      }
                      rows={12}
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="stack">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Planning Sources</p>
                  <h2>What the planner used</h2>
                </div>
              </div>
              {plan.sources.length ? (
                <div className="card-grid">
                  {plan.sources.map((source, index) => (
                    <article key={`${source.title}-${index}`} className="content-card">
                      <h3>{source.title}</h3>
                      <p className="meta-label">
                        {prettyLabel(source.bucket || "general")} • {source.publisher}
                        {source.published_at ? ` • ${source.published_at}` : ""}
                      </p>
                      <div className="analysis-box analysis-box-tall">{source.snippet}</div>
                      {source.url && (
                        <a className="inline-link" href={source.url} target="_blank" rel="noreferrer">
                          Open source
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted">
                  No supporting sources were found. You can still approve the run, but technology-heavy questions may
                  block in technical review.
                </p>
              )}
            </div>

            <div className="actions">
              <button className="button subtle" type="button" disabled={saveBusy || approveBusy} onClick={() => void savePlanDraft()}>
                {saveBusy ? "Saving..." : "Save Draft"}
              </button>
              <button className="button primary" type="button" disabled={approveBusy || saveBusy} onClick={() => void handleApprovePlan()}>
                {approveBusy ? "Approving..." : "Approve Plan and Start Run"}
              </button>
              {reportHref && run?.status === "COMPLETED" && (
                <Link className="button subtle" href={reportHref}>
                  Open Report
                </Link>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Problem Positioning</p>
            <h2>How the run is framed and handed off</h2>
            <p className="hero-copy">
              This is the only thing the Ask page needs to show after planning: how InvestorCrew positions the problem,
              what each report should focus on, and whether the final discussion is ready.
            </p>
          </div>
        </div>

        {plan ? (
          <div className="stack">
            <div className="section-grid">
              <article className="summary-card">
                <span className="meta-label">Asset Overview</span>
                <div className="analysis-box analysis-box-tall">{plan.asset_overview}</div>
              </article>
              <article className="summary-card">
                <span className="meta-label">What Kind of Bet Is This?</span>
                <div className="analysis-box">
                  Primary: {plan.primary_strategy}
                  {"\n"}
                  Secondary: {plan.secondary_strategies.length ? plan.secondary_strategies.join(", ") : "None"}
                  {"\n\n"}
                  {plan.strategy_rationale}
                </div>
              </article>
              <article className="summary-card">
                <span className="meta-label">Key Questions</span>
                <div className="analysis-box analysis-box-tall">
                  {plan.key_study_questions.map((item) => `• ${item}`).join("\n")}
                </div>
              </article>
              <article className="summary-card">
                <span className="meta-label">Source Coverage Summary</span>
                <div className="analysis-box analysis-box-tall">
                  {Object.entries(plan.source_buckets)
                    .map(([bucket, count]) => `• ${prettyLabel(bucket)}: ${count}`)
                    .join("\n")}
                  {plan.coverage_gaps.length ? `\n\nGaps:\n${plan.coverage_gaps.map((item) => `• ${prettyLabel(item)}`).join("\n")}` : ""}
                </div>
              </article>
              <article className="summary-card">
                <span className="meta-label">Run Status</span>
                <div className="analysis-box">
                  {run
                    ? `Status: ${run.status}\nCompany: ${run.company_name ?? plan.company_name ?? "Pending"}\nRouting: ${
                        ((run.classification ?? {}) as Record<string, unknown>)["category"] ?? planClassification["category"] ?? "Pending"
                      }`
                    : "No run started yet. Approve the plan to hand it off to the diligence teams and investor panel."}
                </div>
                {reportHref && run?.status === "COMPLETED" && (
                  <Link className="button subtle" href={reportHref}>
                    Open Final Discussion
                  </Link>
                )}
                {run?.status === "FAILED" && <p className="error-text">{run.error ?? "Run failed"}</p>}
              </article>
            </div>

            <div className="stack">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Report Handoff</p>
                  <h2>How each downstream team should think</h2>
                </div>
              </div>
              <div className="card-grid">
                {promptOrder(plan.prompt_pack).map((key) => (
                  <article key={key} className="content-card">
                    <h3>{prettyLabel(key)}</h3>
                    <p className="muted">{promptHelper(key)}</p>
                    <div className="analysis-box analysis-box-xl">{plan.prompt_pack[key]}</div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <p className="muted">Generate a planning draft to see how InvestorCrew will frame the problem and pass it into the reports.</p>
        )}
      </section>
    </>
  );
}
