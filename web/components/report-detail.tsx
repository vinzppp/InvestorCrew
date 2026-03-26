"use client";

import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";

import { createSelfReview, getReport, getReportArtifactUrl } from "@/lib/api";
import { ReportDetail as ReportDetailType } from "@/lib/types";

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  return String(value);
}

function renderList(value: unknown, empty = "n/a"): string {
  if (!Array.isArray(value) || !value.length) return empty;
  return value.map((item) => `• ${String(item)}`).join("\n");
}

function renderMetricMap(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "n/a";
  const entries = Object.entries(value as Record<string, unknown>);
  if (!entries.length) return "n/a";
  return entries.map(([key, item]) => `${key}: ${String(item)}`).join("\n");
}

function voteCounts(votes: Array<Record<string, unknown>>, proposalId: string): Record<string, number> {
  return votes
    .filter((vote) => vote.proposal_id === proposalId)
    .reduce<Record<string, number>>((accumulator, vote) => {
      const key = String(vote.vote ?? "unknown");
      accumulator[key] = (accumulator[key] ?? 0) + 1;
      return accumulator;
    }, {});
}

function ScrollableTextBlock({ label, text }: { label: string; text: unknown }) {
  return (
    <div className="analysis-block">
      <span className="meta-label">{label}</span>
      <div className="analysis-box analysis-box-tall">{renderValue(text)}</div>
    </div>
  );
}

function DiligenceSection({
  eyebrow,
  title,
  children
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

export function ReportDetail({ reportId, companyId }: { reportId: string; companyId: string }) {
  const [detail, setDetail] = useState<ReportDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);

  useEffect(() => {
    void getReport(reportId)
      .then(setDetail)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load report"));
  }, [reportId]);

  const finalResult = useMemo(() => (detail?.run.final_result ?? {}) as Record<string, unknown>, [detail]);
  const diligencePacket = useMemo(
    () => ((finalResult.diligence_packet as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>,
    [finalResult]
  );
  const committeeMemo = useMemo(
    () => ((finalResult.committee_memo as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>,
    [finalResult]
  );
  const committeeReasoning = useMemo(
    () => ((finalResult.committee_reasoning as unknown[] | undefined) ?? []).map(String),
    [finalResult]
  );
  const analyses = useMemo(() => (finalResult.analyses as Array<Record<string, unknown>> | undefined) ?? [], [finalResult]);
  const discussionLog = useMemo(
    () => (finalResult.discussion_log as Array<Record<string, unknown>> | undefined) ?? [],
    [finalResult]
  );
  const technicalReviews = useMemo(
    () => (finalResult.technical_review_rounds as Array<Record<string, unknown>> | undefined) ?? [],
    [finalResult]
  );

  async function runSelfReview() {
    setReviewBusy(true);
    setError(null);
    try {
      await createSelfReview(reportId);
      const refreshed = await getReport(reportId);
      setDetail(refreshed);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to generate self-review");
    } finally {
      setReviewBusy(false);
    }
  }

  if (!detail) {
    return (
      <section className="panel panel-large">
        <p className="muted">Loading report...</p>
      </section>
    );
  }

  const disposition = renderValue(finalResult.final_disposition ?? "watchlist");
  const blockedReason = finalResult.blocked_reason;
  const technicalReport = (diligencePacket.technical_report ?? {}) as Record<string, unknown>;
  const stockReport = (diligencePacket.stock_report ?? {}) as Record<string, unknown>;
  const industryReport = (diligencePacket.industry_report ?? {}) as Record<string, unknown>;
  const macroReport = (diligencePacket.economic_report ?? {}) as Record<string, unknown>;

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Executive View</p>
            <h2>{detail.run.question}</h2>
            <p className="hero-copy">
              This view starts with the committee conclusion, then lets you read the diligence, investor discussion,
              proposals, and final votes without exposing raw markdown or system logs.
            </p>
          </div>
          <span className={`status-pill ${disposition === "invest" ? "good" : disposition === "no_invest" ? "bad" : "warn"}`}>
            {disposition}
          </span>
        </div>

        <div className="section-grid">
          <article className="summary-card">
            <span className="meta-label">Company</span>
            <strong>{detail.run.company_name ?? detail.run.company_ticker ?? "N/A"}</strong>
            {detail.run.company_ticker && (
              <Link href={`/library/${companyId}`} className="inline-link">
                Open company workspace
              </Link>
            )}
          </article>
          <article className="summary-card">
            <span className="meta-label">Conclusion</span>
            <div className="analysis-box analysis-box-tall">
              {committeeMemo.conclusion
                ? renderValue(committeeMemo.conclusion)
                : blockedReason
                  ? renderValue(blockedReason)
                  : "Conclusion unavailable."}
            </div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Exports</span>
            <div className="stack compact-stack">
              {detail.run.markdown_path && (
                <a className="inline-link" href={getReportArtifactUrl(reportId, "markdown")} target="_blank" rel="noreferrer">
                  Download report
                </a>
              )}
              {detail.run.json_path && (
                <a className="inline-link" href={getReportArtifactUrl(reportId, "json")} target="_blank" rel="noreferrer">
                  Download JSON
                </a>
              )}
            </div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Disposition</span>
            <div className="analysis-box">
              {renderValue(committeeMemo.disposition || disposition)}
              {blockedReason ? `\n\nBlocked: ${renderValue(blockedReason)}` : ""}
            </div>
          </article>
        </div>

        <div className="card-grid">
          <article className="summary-card">
            <span className="meta-label">Thesis</span>
            <div className="analysis-box analysis-box-tall">{renderValue(committeeMemo.thesis)}</div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Opportunities</span>
            <div className="analysis-box analysis-box-tall">{renderList(committeeMemo.opportunities, "No committee opportunities recorded.")}</div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Risks</span>
            <div className="analysis-box analysis-box-tall">{renderList(committeeMemo.risks, "No committee risks recorded.")}</div>
          </article>
          <article className="summary-card">
            <span className="meta-label">How The Committee Weighed It</span>
            <div className="analysis-box analysis-box-tall">{renderValue(committeeMemo.weighing)}</div>
          </article>
        </div>
      </section>

      {(Object.keys(technicalReport).length > 0 || technicalReviews.length > 0) && (
        <DiligenceSection eyebrow="Technical Diligence" title="Technical mechanism, feasibility, and review gate">
          <div className="card-grid">
            <article className="content-card">
              <h3>Technical Report</h3>
              <div className="stack compact-stack">
                <ScrollableTextBlock label="What It Is" text={technicalReport.what_it_is} />
                <ScrollableTextBlock label="Scientific Mechanism" text={technicalReport.scientific_mechanism} />
                <ScrollableTextBlock label="Proof Status" text={technicalReport.proof_status} />
                <ScrollableTextBlock label="Feasibility" text={technicalReport.feasibility} />
                <ScrollableTextBlock label="Engineering Bottlenecks" text={renderList(technicalReport.engineering_bottlenecks)} />
                <ScrollableTextBlock label="Timeline" text={technicalReport.timeline} />
                <ScrollableTextBlock label="Regulatory Path" text={technicalReport.regulatory_path} />
                <ScrollableTextBlock label="Competitive Landscape" text={renderList(technicalReport.competitive_landscape)} />
                <ScrollableTextBlock label="Failure Modes" text={renderList(technicalReport.failure_modes)} />
              </div>
            </article>
            {technicalReviews.map((review, index) => (
              <article key={`review-${index}`} className="content-card">
                <h3>Technical Review Round {renderValue(review.round_index)}</h3>
                <div className="stack compact-stack">
                  <ScrollableTextBlock label="Summary" text={review.summary} />
                  <ScrollableTextBlock
                    label="Scores"
                    text={`Overall ${renderValue(review.overall_score)}\nDepth ${renderValue(review.depth_score)}\nEvidence ${renderValue(
                      review.evidence_quality_score
                    )}\nFeasibility ${renderValue(review.feasibility_reasoning_score)}\nCompetitive ${renderValue(
                      review.competitive_analysis_score
                    )}\nClarity ${renderValue(review.clarity_score)}`}
                  />
                  <ScrollableTextBlock label="Findings" text={renderList(review.findings)} />
                  <ScrollableTextBlock label="Required Revisions" text={renderList(review.required_revisions)} />
                </div>
              </article>
            ))}
          </div>
        </DiligenceSection>
      )}

      {Object.keys(stockReport).length > 0 && (
        <DiligenceSection eyebrow="Stock Diligence" title="Business quality, valuation, and balance sheet">
          <div className="card-grid">
            <article className="content-card">
              <h3>Business Model</h3>
              <div className="stack compact-stack">
                <ScrollableTextBlock label="Business Summary" text={stockReport.business_summary} />
                <ScrollableTextBlock label="Valuation View" text={stockReport.cheap_or_expensive} />
                <ScrollableTextBlock label="Segment Mix" text={renderMetricMap(stockReport.segment_mix)} />
              </div>
            </article>
            <article className="content-card">
              <h3>Metrics</h3>
              <div className="stack compact-stack">
                <ScrollableTextBlock label="Selected Metrics" text={renderList(stockReport.selected_metrics)} />
                <ScrollableTextBlock label="Operating Metrics" text={renderMetricMap(stockReport.operating_metrics)} />
                <ScrollableTextBlock label="Valuation Metrics" text={renderMetricMap(stockReport.valuation_metrics)} />
                <ScrollableTextBlock label="Balance Sheet / Runway" text={renderMetricMap(stockReport.balance_sheet_metrics)} />
                <ScrollableTextBlock label="Open Unknowns" text={renderList(stockReport.open_unknowns)} />
              </div>
            </article>
          </div>
        </DiligenceSection>
      )}

      {Object.keys(industryReport).length > 0 && (
        <DiligenceSection eyebrow="Industry Diligence" title="Market size, competition, and customer demand">
          <div className="card-grid">
            <article className="content-card">
              <h3>Industry Overview</h3>
              <div className="stack compact-stack">
                <ScrollableTextBlock label="Summary" text={industryReport.summary} />
                <ScrollableTextBlock label="Market Size" text={industryReport.market_size} />
                <ScrollableTextBlock label="Market Structure" text={industryReport.market_structure} />
                <ScrollableTextBlock label="Customer Overview" text={industryReport.customer_overview} />
              </div>
            </article>
            <article className="content-card">
              <h3>Industry Drivers And Risks</h3>
              <div className="stack compact-stack">
                <ScrollableTextBlock label="Growth Drivers" text={renderList(industryReport.growth_drivers)} />
                <ScrollableTextBlock label="Competitors" text={renderList(industryReport.competitors)} />
                <ScrollableTextBlock label="Opportunities" text={renderList(industryReport.opportunities)} />
                <ScrollableTextBlock label="Risks" text={renderList(industryReport.risks)} />
              </div>
            </article>
          </div>
        </DiligenceSection>
      )}

      {Object.keys(macroReport).length > 0 && (
        <DiligenceSection eyebrow="Macro Diligence" title="Regime summary and market conditions">
          <div className="card-grid">
            <article className="content-card">
              <h3>Macro View</h3>
              <div className="stack compact-stack">
                <ScrollableTextBlock label="Summary" text={macroReport.summary} />
                <ScrollableTextBlock label="Key Indicators" text={renderMetricMap(macroReport.core_metrics)} />
                <ScrollableTextBlock label="Richest Market" text={macroReport.richest_market} />
                <ScrollableTextBlock label="Cheapest Market" text={macroReport.cheapest_market} />
              </div>
            </article>
          </div>
        </DiligenceSection>
      )}

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Investor Panel</p>
            <h2>Full investor discussion</h2>
          </div>
        </div>
        <div className="investor-grid">
          {analyses.map((analysis) => (
            <article key={renderValue(analysis.investor_slug ?? analysis.investor_name)} className="content-card">
              <h3>{renderValue(analysis.investor_name)}</h3>
              <div className="stack compact-stack investor-analysis-stack">
                <ScrollableTextBlock label="Philosophy Fit" text={analysis.situation} />
                <ScrollableTextBlock label="Edge And Evidence" text={analysis.interpretation} />
                <ScrollableTextBlock label="Upside Case" text={analysis.thesis} />
                <ScrollableTextBlock label="Downside And Falsification" text={analysis.falsification} />
                <ScrollableTextBlock label="Portfolio Fit" text={analysis.portfolio} />
                <ScrollableTextBlock label="Final Stance" text={analysis.conclusion} />
                {Array.isArray(analysis.updates) && analysis.updates.length > 0 && (
                  <ScrollableTextBlock label="Updates" text={analysis.updates.map((item) => `• ${item}`).join("\n")} />
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Investment Committee</p>
            <h2>Committee proposals and investor votes</h2>
          </div>
        </div>
        {!!committeeReasoning.length && (
          <div className="section-grid">
            {committeeReasoning.map((reason, index) => (
              <article key={`reason-${index}`} className="summary-card">
                <span className="meta-label">Committee Reasoning {index + 1}</span>
                <div className="analysis-box analysis-box-tall">{reason}</div>
              </article>
            ))}
          </div>
        )}
        {detail.proposals.length ? (
          <div className="stack">
            <div className="card-grid">
              {detail.proposals.map((proposal) => {
                const counts = voteCounts(detail.votes, String(proposal.proposal_id));
                return (
                  <article key={String(proposal.proposal_id)} className="content-card">
                    <h3>{renderValue(proposal.title)}</h3>
                    <div className="stack compact-stack">
                      <ScrollableTextBlock label="Action" text={proposal.action} />
                      <ScrollableTextBlock label="Thesis" text={proposal.thesis} />
                      <ScrollableTextBlock label="Drivers" text={renderList(proposal.key_drivers)} />
                      <ScrollableTextBlock label="Risks" text={renderList(proposal.key_risks)} />
                      <ScrollableTextBlock label="Portfolio Note" text={proposal.portfolio_note} />
                      <div className="chip-scroll">
                        <div className="chip-row nowrap-row">
                          {Object.entries(counts).map(([key, value]) => (
                            <span key={key} className="metric-chip">
                              {key}: {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="table-scroll">
              <table className="vote-table">
                <thead>
                  <tr>
                    <th>Investor</th>
                    {detail.proposals.map((proposal) => (
                      <th key={String(proposal.proposal_id)}>{renderValue(proposal.proposal_id)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {analyses.map((analysis) => (
                    <tr key={renderValue(analysis.investor_slug)}>
                      <td>{renderValue(analysis.investor_name)}</td>
                      {detail.proposals.map((proposal) => {
                        const record = detail.votes.find(
                          (vote) =>
                            vote.proposal_id === proposal.proposal_id &&
                            vote.investor_name === analysis.investor_name
                        );
                        return (
                          <td key={`${renderValue(analysis.investor_slug)}-${renderValue(proposal.proposal_id)}`}>
                            {renderValue(record?.vote ?? "n/a")}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <article className="content-card">
            <h3>No-invest outcome</h3>
            <div className="analysis-box analysis-box-tall">
              {committeeMemo.conclusion
                ? renderValue(committeeMemo.conclusion)
                : blockedReason
                  ? renderValue(blockedReason)
                  : "No proposal cleared the bar for action."}
            </div>
          </article>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Discussion Log</p>
            <h2>Panel and committee back-and-forth</h2>
            <p className="hero-copy">This keeps the human discussion only and hides system orchestration noise.</p>
          </div>
        </div>
        <ol className="timeline">
          {discussionLog.map((entry, index) => (
            <li key={`${entry.speaker}-${index}`} className="timeline-item">
              <div className="timeline-header">
                <span className="timeline-stage">{renderValue(entry.section)}</span>
                <span className="timeline-actor">{renderValue(entry.speaker)}</span>
                <span className="timeline-time">{renderValue(entry.role)}</span>
              </div>
              <div className="analysis-box analysis-box-xl">{renderValue(entry.content)}</div>
            </li>
          ))}
          {!discussionLog.length && <p className="muted">No committee discussion log was recorded for this report.</p>}
        </ol>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Self Review</p>
            <h2>On-demand critique of the finished report</h2>
          </div>
          <button className="button subtle" onClick={() => void runSelfReview()} disabled={reviewBusy}>
            {reviewBusy ? "Reviewing..." : "Run Self Review"}
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
        <div className="card-grid">
          {detail.self_reviews.map((review) => (
            <article key={review.review_id} className="review-card">
              <h3>{review.created_at.slice(0, 19)}</h3>
              <ScrollableTextBlock label="Summary" text={review.summary} />
              <div className="stack compact-stack">
                {review.recommendations.map((recommendation, index) => (
                  <article key={`${review.review_id}-${index}`} className="summary-card">
                    <span className="meta-label">
                      {recommendation.category} • {recommendation.priority}
                    </span>
                    <div className="analysis-box">{recommendation.recommendation}</div>
                    <div className="analysis-box muted-box">{recommendation.rationale}</div>
                  </article>
                ))}
              </div>
            </article>
          ))}
          {!detail.self_reviews.length && (
            <p className="muted">Run self-review to see prompt, data, and orchestration suggestions for this report.</p>
          )}
        </div>
      </section>
    </>
  );
}
