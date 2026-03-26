"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getCompany } from "@/lib/api";
import { CompanyDetail, ReportSummary } from "@/lib/types";

function groupReportsByDate(reports: ReportSummary[]): Record<string, ReportSummary[]> {
  return reports.reduce<Record<string, ReportSummary[]>>((groups, report) => {
    const key = report.created_at.slice(0, 10);
    groups[key] = groups[key] ? [...groups[key], report] : [report];
    return groups;
  }, {});
}

function renderMetricList(metrics: Record<string, unknown>): string {
  const entries = Object.entries(metrics);
  if (!entries.length) return "No curated metrics in the current company record.";
  return entries.map(([key, value]) => `${key}: ${String(value)}`).join("\n");
}

function renderSourceLibrary(company: CompanyDetail["company"]): Array<{
  title: string;
  publisher: string;
  published_at: string | null;
  url: string;
  snippet: string;
}> {
  const technologySources = Array.isArray(company.technology.sources)
    ? (company.technology.sources as Array<Record<string, unknown>>)
    : [];
  const stockSources = Array.isArray(company.stock.sources)
    ? (company.stock.sources as Array<Record<string, unknown>>)
    : [];
  return [...technologySources, ...stockSources].map((source) => ({
    title: String(source.title ?? company.name),
    publisher: String(source.publisher ?? "Source"),
    published_at: source.published_at ? String(source.published_at) : null,
    url: String(source.url ?? ""),
    snippet: String(source.snippet ?? source.note ?? "Source note unavailable.")
  }));
}

export function CompanyWorkspace({ companyId }: { companyId: string }) {
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getCompany(companyId)
      .then((nextDetail) => {
        setDetail(nextDetail);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load company"));
  }, [companyId]);

  const groupedReports = useMemo(() => groupReportsByDate(detail?.reports ?? []), [detail]);

  if (!detail) {
    return (
      <section className="panel panel-large">
        <p className="muted">Loading company workspace...</p>
      </section>
    );
  }

  const company = detail.company;
  const sourceLibrary = renderSourceLibrary(company);
  const productSummary = String(company.technology.summary ?? company.description);
  const customerSummary =
    Object.keys(company.stock.segment_mix ?? {}).length > 0
      ? Object.entries(company.stock.segment_mix as Record<string, unknown>)
          .map(([segment, weight]) => `${segment}: ${String(weight)}`)
          .join("\n")
      : String(company.technology.world_impact ?? "Customer coverage has not been richly curated for this company yet.");
  const competition = Array.isArray(company.technology.competitor_technologies)
    ? (company.technology.competitor_technologies as Array<unknown>).map(String).join("\n")
    : "Competitive landscape is not richly curated in this company record yet.";

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{company.ticker}</p>
            <h2>{company.name}</h2>
            <p className="hero-copy">{company.description}</p>
          </div>
          <span className="status-pill neutral">{company.archetype}</span>
        </div>

        <div className="section-grid">
          <article className="summary-card">
            <span className="meta-label">Overview</span>
            <div className="analysis-box analysis-box-tall">{company.description}</div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Industry Snapshot</span>
            <div className="analysis-box analysis-box-tall">
              Sector: {company.sector}
              {"\n"}
              Industry: {company.industry}
              {"\n"}
              Archetype: {company.archetype}
            </div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Products And Technology</span>
            <div className="analysis-box analysis-box-tall">{productSummary}</div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Customers And Go-To-Market</span>
            <div className="analysis-box analysis-box-tall">{customerSummary}</div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Leadership</span>
            <div className="analysis-box analysis-box-tall">
              Leadership detail should be checked through proxy filings, investor materials, and leadership interviews.
            </div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Shareholders</span>
            <div className="analysis-box analysis-box-tall">
              Shareholder detail should be checked through governance filings, financing history, and major-holder disclosures.
            </div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Strategy And Priorities</span>
            <div className="analysis-box analysis-box-tall">
              {String(company.technology.preferred_rationale ?? company.technology.feasibility ?? company.description)}
            </div>
          </article>
          <article className="summary-card">
            <span className="meta-label">Competitive Landscape</span>
            <div className="analysis-box analysis-box-tall">{competition}</div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Key Metrics</p>
            <h2>Stock and valuation snapshot</h2>
          </div>
        </div>
        <div className="card-grid">
          <article className="content-card">
            <h3>Operating Metrics</h3>
            <div className="analysis-box analysis-box-tall">
              {renderMetricList((company.stock.operating_metrics as Record<string, unknown>) ?? {})}
            </div>
          </article>
          <article className="content-card">
            <h3>Valuation Metrics</h3>
            <div className="analysis-box analysis-box-tall">
              {renderMetricList((company.stock.valuation_metrics as Record<string, unknown>) ?? {})}
            </div>
          </article>
          <article className="content-card">
            <h3>Balance Sheet</h3>
            <div className="analysis-box analysis-box-tall">
              {renderMetricList((company.stock.balance_sheet_metrics as Record<string, unknown>) ?? {})}
            </div>
          </article>
          <article className="content-card">
            <h3>Supplemental Metrics</h3>
            <div className="analysis-box analysis-box-tall">
              {renderMetricList((company.stock.supplemental_metrics as Record<string, unknown>) ?? {})}
            </div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Source Library</p>
            <h2>Curated company reference points</h2>
          </div>
        </div>
        {sourceLibrary.length ? (
          <div className="card-grid">
            {sourceLibrary.map((source, index) => (
              <article key={`${source.title}-${index}`} className="content-card">
                <h3>{source.title}</h3>
                <p className="meta-label">
                  {source.publisher}
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
          <p className="muted">No source library is stored for this company yet.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Report History</p>
            <h2>Saved runs by date</h2>
          </div>
        </div>
        <div className="stack">
          {Object.entries(groupedReports).map(([date, reports]) => (
            <div key={date} className="report-group">
              <h3>{date}</h3>
              <div className="stack">
                {reports.map((report) => (
                  <Link key={report.id} href={`/library/${companyId}/reports/${report.id}`} className="report-row">
                    <div>
                      <strong>{report.question}</strong>
                      <p>{report.status}</p>
                    </div>
                    <span>{report.completed_at ? report.completed_at.slice(11, 19) : "Running"}</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
          {!detail.reports.length && <p className="muted">No saved reports for this company yet.</p>}
          {error && <p className="error-text">{error}</p>}
        </div>
      </section>
    </>
  );
}
