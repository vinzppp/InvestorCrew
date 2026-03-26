"use client";

import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";

import { StructuredValue, formatLabel } from "@/components/data-view";
import { createSelfReview, getReport, getReportArtifactUrl } from "@/lib/api";
import { ReportDetail as ReportDetailType } from "@/lib/types";

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  return String(value);
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

function MetricDictionary({
  title,
  values
}: {
  title: string;
  values: Record<string, unknown> | undefined;
}) {
  if (!values || !Object.keys(values).length) {
    return null;
  }
  return (
    <div className="stack compact-stack">
      <span className="meta-label">{title}</span>
      <dl className="kv-grid">
        {Object.entries(values).map(([key, value]) => (
          <div key={key} className="kv-item">
            <dt>{formatLabel(key)}</dt>
            <dd>{renderValue(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function ScrollableTextBlock({
  label,
  text
}: {
  label: string;
  text: unknown;
}) {
  return (
    <div className="analysis-block">
      <span className="meta-label">{label}</span>
      <div className="analysis-box">{renderValue(text)}</div>
    </div>
  );
}

function ExpandSection({
  title,
  eyebrow,
  subtitle,
  children,
  defaultOpen = false
}: {
  title: string;
  eyebrow: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details className="expand-section" open={defaultOpen}>
      <summary>
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
          {subtitle && <p className="hero-copy">{subtitle}</p>}
        </div>
        <span className="expand-hint">{defaultOpen ? "Collapse" : "Expand"}</span>
      </summary>
      <div className="details-body">{children}</div>
    </details>
  );
}

function DiligenceArtifact({ artifact }: { artifact: ReportDetailType["artifacts"][number] }) {
  const payload = artifact.payload;

  if (artifact.artifact_type === "technical_report") {
    return (
      <article className="content-card">
        <h3>{artifact.title}</h3>
        <div className="stack compact-stack">
          <p>{renderValue(payload.summary)}</p>
          <div className="section-grid">
            <div className="summary-card">
              <span className="meta-label">What It Is</span>
              <p>{renderValue(payload.what_it_is)}</p>
            </div>
            <div className="summary-card">
              <span className="meta-label">World Impact</span>
              <p>{renderValue(payload.world_impact)}</p>
            </div>
            <div className="summary-card">
              <span className="meta-label">Feasibility</span>
              <p>{renderValue(payload.feasibility)}</p>
            </div>
            <div className="summary-card">
              <span className="meta-label">Preferred Technology</span>
              <p>{renderValue(payload.preferred_technology)}</p>
              <p className="muted">{renderValue(payload.preferred_rationale)}</p>
            </div>
          </div>
          <div className="section-grid">
            <div className="summary-card">
              <span className="meta-label">Requirements</span>
              <StructuredValue value={payload.requirements ?? []} compact />
            </div>
            <div className="summary-card">
              <span className="meta-label">Constraints</span>
              <StructuredValue value={payload.constraints ?? []} compact />
            </div>
            <div className="summary-card">
              <span className="meta-label">Competitive Landscape</span>
              <StructuredValue value={payload.competitive_landscape ?? []} compact />
            </div>
            <div className="summary-card">
              <span className="meta-label">Open Unknowns</span>
              <StructuredValue value={payload.open_unknowns ?? []} compact />
            </div>
          </div>
        </div>
      </article>
    );
  }

  if (artifact.artifact_type === "stock_report") {
    return (
      <article className="content-card">
        <h3>{artifact.title}</h3>
        <div className="section-grid">
          <div className="summary-card">
            <span className="meta-label">Company</span>
            <strong>
              {renderValue(payload.company_name)} ({renderValue(payload.ticker)})
            </strong>
            <p>{renderValue(payload.business_summary)}</p>
          </div>
          <div className="summary-card">
            <span className="meta-label">Market Read</span>
            <strong>{renderValue(payload.cheap_or_expensive)}</strong>
            <p>As of {renderValue(payload.as_of)}</p>
          </div>
          <div className="summary-card">
            <span className="meta-label">Selected Metrics</span>
            <StructuredValue value={payload.selected_metrics ?? []} compact />
          </div>
          <div className="summary-card">
            <span className="meta-label">Missing Metrics</span>
            <StructuredValue value={payload.missing_metrics ?? []} compact />
          </div>
        </div>
        <div className="section-grid">
          <MetricDictionary title="Operating Metrics" values={payload.operating_metrics as Record<string, unknown>} />
          <MetricDictionary title="Valuation Metrics" values={payload.valuation_metrics as Record<string, unknown>} />
          <MetricDictionary
            title="Balance Sheet Metrics"
            values={payload.balance_sheet_metrics as Record<string, unknown>}
          />
          <div className="summary-card">
            <span className="meta-label">Segment Mix</span>
            <StructuredValue value={payload.segment_mix ?? {}} compact />
          </div>
        </div>
      </article>
    );
  }

  if (artifact.artifact_type === "economic_report") {
    return (
      <article className="content-card">
        <h3>{artifact.title}</h3>
        <div className="section-grid">
          <div className="summary-card">
            <span className="meta-label">Summary</span>
            <p>{renderValue(payload.summary)}</p>
          </div>
          <div className="summary-card">
            <span className="meta-label">Richest Market</span>
            <strong>{renderValue(payload.richest_market)}</strong>
          </div>
          <div className="summary-card">
            <span className="meta-label">Cheapest Market</span>
            <strong>{renderValue(payload.cheapest_market)}</strong>
          </div>
          <div className="summary-card">
            <span className="meta-label">Selected Metrics</span>
            <StructuredValue value={payload.selected_metrics ?? []} compact />
          </div>
        </div>
        <MetricDictionary title="Core Metrics" values={payload.core_metrics as Record<string, unknown>} />
        <div className="summary-card">
          <span className="meta-label">Market Comparison</span>
          <StructuredValue value={payload.market_comparison ?? []} compact />
        </div>
      </article>
    );
  }

  return (
    <article className="content-card">
      <h3>{artifact.title}</h3>
      <StructuredValue value={payload} />
    </article>
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

  const finalResult = useMemo(() => {
    return (detail?.run.final_result ?? {}) as Record<string, unknown>;
  }, [detail]);

  const diligencePacket = useMemo(() => {
    return ((finalResult.diligence_packet as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  }, [finalResult]);

  const metricSelections = useMemo(() => {
    return (diligencePacket.metric_selections as Array<Record<string, unknown>> | undefined) ?? [];
  }, [diligencePacket]);

  const analyses = useMemo(() => {
    return (finalResult.analyses as Array<Record<string, unknown>> | undefined) ?? [];
  }, [finalResult]);

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

  const classification = (detail.run.classification ?? {}) as Record<string, unknown>;
  const stockReport = (diligencePacket.stock_report ?? {}) as Record<string, unknown>;
  const techReport = (diligencePacket.technical_report ?? {}) as Record<string, unknown>;
  const economicReport = (diligencePacket.economic_report ?? {}) as Record<string, unknown>;
  const supplementalNotes = (diligencePacket.supplemental_notes as unknown[]) ?? [];

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Executive View</p>
            <h2>{detail.run.question}</h2>
            <p className="hero-copy">
              Start with the high-level crew read here, then expand the diligence, proposals, transcript, and review
              sections only when you want the deeper mechanics.
            </p>
          </div>
          <span className="status-pill neutral">{detail.run.status}</span>
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
            <span className="meta-label">Routing</span>
            <strong>{renderValue(classification.category)}</strong>
            <p>{renderValue(classification.reason)}</p>
          </article>
          <article className="summary-card">
            <span className="meta-label">Crew Output</span>
            <strong>{detail.proposals.length} proposals</strong>
            <p>{renderValue(finalResult.follow_up_rounds_used)} follow-up rounds used</p>
          </article>
          <article className="summary-card">
            <span className="meta-label">Exports</span>
            <div className="stack compact-stack">
              {detail.run.markdown_path && (
                <a
                  className="inline-link"
                  href={getReportArtifactUrl(reportId, "markdown")}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download report
                </a>
              )}
              {detail.run.json_path && (
                <a
                  className="inline-link"
                  href={getReportArtifactUrl(reportId, "json")}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download JSON
                </a>
              )}
            </div>
          </article>
        </div>

        <div className="section-grid">
          {Boolean(techReport.summary) && (
            <article className="summary-card">
              <span className="meta-label">Technical Read</span>
              <p>{renderValue(techReport.summary)}</p>
            </article>
          )}
          {Boolean(stockReport.cheap_or_expensive) && (
            <article className="summary-card">
              <span className="meta-label">Stock Read</span>
              <p>{renderValue(stockReport.cheap_or_expensive)}</p>
            </article>
          )}
          {Boolean(economicReport.summary) && (
            <article className="summary-card">
              <span className="meta-label">Macro Read</span>
              <p>{renderValue(economicReport.summary)}</p>
            </article>
          )}
          {detail.proposals[0] && (
            <article className="summary-card">
              <span className="meta-label">Top Proposal</span>
              <strong>{renderValue(detail.proposals[0].title)}</strong>
              <p>{renderValue(detail.proposals[0].thesis)}</p>
            </article>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Investor Panel</p>
            <h2>Full investor discussion</h2>
            <p className="hero-copy">This stays expanded by default so you can read the crew without drilling down.</p>
          </div>
        </div>
        <div className="investor-grid">
          {analyses.map((analysis) => (
            <article key={String(analysis.investor_slug ?? analysis.investor_name)} className="content-card">
              <h3>{renderValue(analysis.investor_name)}</h3>
              <div className="stack compact-stack investor-analysis-stack">
                <ScrollableTextBlock label="Situation" text={analysis.situation} />
                <ScrollableTextBlock label="Interpretation" text={analysis.interpretation} />
                <ScrollableTextBlock label="Thesis" text={analysis.thesis} />
                <ScrollableTextBlock label="Falsification" text={analysis.falsification} />
                <ScrollableTextBlock label="Portfolio Fit" text={analysis.portfolio} />
                <ScrollableTextBlock label="Conclusion and Vote" text={analysis.conclusion} />
                {Array.isArray(analysis.updates) && analysis.updates.length > 0 && (
                  <ScrollableTextBlock label="Updates" text={analysis.updates.map((item) => `• ${item}`).join("\n")} />
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <ExpandSection
          eyebrow="Metric Plan"
          title="Chosen lenses before the debate"
          subtitle="Metric selection stays tucked away at first so the report opens with conclusions rather than setup."
        >
          <div className="card-grid">
            {metricSelections.map((selection, index) => (
              <article key={`${selection.scope as string}-${index}`} className="content-card">
                <h3>{renderValue(selection.scope)}</h3>
                <p className="muted">{renderValue(selection.rationale)}</p>
                <div className="stack compact-stack">
                  <div>
                    <span className="meta-label">Lens</span>
                    <strong>{renderValue(selection.lens)}</strong>
                  </div>
                  <div>
                    <span className="meta-label">Chosen Metrics</span>
                    <StructuredValue value={selection.chosen_metrics ?? []} compact />
                  </div>
                  <div>
                    <span className="meta-label">Excluded Metrics</span>
                    <StructuredValue value={selection.excluded_metrics ?? []} compact />
                  </div>
                </div>
              </article>
            ))}
          </div>
        </ExpandSection>
      </section>

      <section className="panel">
        <ExpandSection
          eyebrow="Due Diligence"
          title="Reports sent to the investor crew"
          subtitle="Technical, stock, and macro packets are still here, but they open only when you want the underlying evidence."
        >
          <div className="section-grid">
            {detail.artifacts.map((artifact, index) => (
              <DiligenceArtifact key={`${artifact.artifact_type}-${index}`} artifact={artifact} />
            ))}
          </div>
        </ExpandSection>
      </section>

      <section className="panel">
        <ExpandSection
          eyebrow="Proposals"
          title="Moderator synthesis and voting"
          subtitle="Proposal drivers and risks now scroll when the lists get long so the cards stay readable."
        >
          <div className="section-grid">
            {detail.proposals.map((proposal, index) => {
              const counts = voteCounts(detail.votes, String(proposal.proposal_id));
              return (
                <article key={`${proposal.proposal_id as string}-${index}`} className="content-card">
                  <h3>{renderValue(proposal.title)}</h3>
                  <div className="stack compact-stack">
                    <div>
                      <span className="meta-label">Action</span>
                      <strong>{renderValue(proposal.action)}</strong>
                    </div>
                    <div>
                      <span className="meta-label">Thesis</span>
                      <p>{renderValue(proposal.thesis)}</p>
                    </div>
                    <div>
                      <span className="meta-label">Horizon</span>
                      <p>{renderValue(proposal.horizon)}</p>
                    </div>
                    <div>
                      <span className="meta-label">Drivers</span>
                      <StructuredValue value={proposal.key_drivers ?? []} compact />
                    </div>
                    <div>
                      <span className="meta-label">Risks</span>
                      <StructuredValue value={proposal.key_risks ?? []} compact />
                    </div>
                    <div>
                      <span className="meta-label">Portfolio Note</span>
                      <p>{renderValue(proposal.portfolio_note)}</p>
                    </div>
                    <div>
                      <span className="meta-label">Vote Mix</span>
                      <StructuredValue value={counts} compact />
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
                  <th>Proposal</th>
                  <th>Investor</th>
                  <th>Vote</th>
                  <th>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {detail.votes.map((vote, index) => (
                  <tr key={`${index}-${vote.proposal_id}`}>
                    <td>{renderValue(vote.proposal_id)}</td>
                    <td>{renderValue(vote.investor_name)}</td>
                    <td>{renderValue(vote.vote)}</td>
                    <td>{renderValue(vote.rationale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ExpandSection>
      </section>

      <section className="panel">
        <ExpandSection
          eyebrow="Transcript"
          title="Full orchestration log"
          subtitle="The live system transcript is still available, but it stays collapsed until you need the exact event trail."
        >
          <ol className="timeline">
            {detail.events.map((event) => (
              <li key={`${event.sequence}-${event.title}`} className="timeline-item">
                <div className="timeline-header">
                  <span className="timeline-stage">{event.stage}</span>
                  <span className="timeline-actor">{event.actor ?? "system"}</span>
                  <span className="timeline-time">{event.created_at.slice(11, 19)}</span>
                </div>
                <strong>{event.title}</strong>
                <div className="timeline-body">
                  <StructuredValue value={event.payload} compact />
                </div>
              </li>
            ))}
          </ol>
        </ExpandSection>
      </section>

      <section className="panel">
        <ExpandSection
          eyebrow="Follow-Up"
          title="Supplemental diligence notes"
          subtitle="Extra requests and missing-evidence notes are grouped separately so they do not crowd the main read."
        >
          <StructuredValue value={supplementalNotes} compact />
        </ExpandSection>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Self Review</p>
            <h2>Suggested process improvements</h2>
            <p className="hero-copy">
              This section inspects the finished report and points out gaps in prompts, evidence, and orchestration.
            </p>
          </div>
          <button className="button subtle" onClick={runSelfReview} disabled={reviewBusy}>
            {reviewBusy ? "Reviewing..." : "Run Self-Review"}
          </button>
        </div>
        <div className="stack">
          {detail.self_reviews.map((review) => (
            <div key={review.review_id} className="review-card">
              <strong>{review.summary}</strong>
              <p className="meta-label">{review.created_at}</p>
              <div className="stack compact-stack">
                {review.recommendations.map((item, index) => (
                  <div key={`${review.review_id}-${index}`} className="summary-card">
                    <span className="meta-label">
                      {item.category} · {item.priority}
                    </span>
                    <div className="analysis-box">{item.recommendation}</div>
                    <div className="analysis-box muted-box">{item.rationale}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!detail.self_reviews.length && <p className="muted">No self-review yet.</p>}
          {error && <p className="error-text">{error}</p>}
        </div>
      </section>
    </>
  );
}
