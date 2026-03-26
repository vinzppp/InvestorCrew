"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getCompany, updateCompany } from "@/lib/api";
import { CompanyDetail, CompanyRecordPayload, ReportSummary } from "@/lib/types";

function groupReportsByDate(reports: ReportSummary[]): Record<string, ReportSummary[]> {
  return reports.reduce<Record<string, ReportSummary[]>>((groups, report) => {
    const key = report.created_at.slice(0, 10);
    groups[key] = groups[key] ? [...groups[key], report] : [report];
    return groups;
  }, {});
}

export function CompanyWorkspace({ companyId }: { companyId: string }) {
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [draft, setDraft] = useState<CompanyRecordPayload | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getCompany(companyId)
      .then((nextDetail) => {
        setDetail(nextDetail);
        setDraft(nextDetail.company);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load company"));
  }, [companyId]);

  const groupedReports = useMemo(() => groupReportsByDate(detail?.reports ?? []), [detail]);

  async function saveCompany() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      await updateCompany(companyId, draft as unknown as Record<string, unknown>);
      const refreshed = await getCompany(companyId);
      setDetail(refreshed);
      setDraft(refreshed.company);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to save company");
    } finally {
      setSaving(false);
    }
  }

  if (!detail || !draft) {
    return <section className="panel panel-large"><p className="muted">Loading company workspace...</p></section>;
  }

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{draft.ticker}</p>
            <h2>{draft.name}</h2>
          </div>
          <span className="status-pill neutral">{draft.archetype}</span>
        </div>
        <div className="stack">
          <label className="field">
            <span>Description</span>
            <textarea
              value={draft.description}
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
              rows={5}
            />
          </label>
          <div className="split-fields">
            <label className="field">
              <span>Sector</span>
              <input value={draft.sector} onChange={(event) => setDraft({ ...draft, sector: event.target.value })} />
            </label>
            <label className="field">
              <span>Industry</span>
              <input value={draft.industry} onChange={(event) => setDraft({ ...draft, industry: event.target.value })} />
            </label>
            <label className="field">
              <span>Archetype</span>
              <input value={draft.archetype} onChange={(event) => setDraft({ ...draft, archetype: event.target.value })} />
            </label>
          </div>
          <label className="field">
            <span>Technology JSON</span>
            <textarea
              value={JSON.stringify(draft.technology, null, 2)}
              onChange={(event) => {
                try {
                  setDraft({ ...draft, technology: JSON.parse(event.target.value) });
                } catch {
                  // Let invalid JSON sit in the textarea until the user fixes it.
                }
              }}
              rows={12}
            />
          </label>
          <label className="field">
            <span>Stock JSON</span>
            <textarea
              value={JSON.stringify(draft.stock, null, 2)}
              onChange={(event) => {
                try {
                  setDraft({ ...draft, stock: JSON.parse(event.target.value) });
                } catch {
                  // Let invalid JSON sit in the textarea until the user fixes it.
                }
              }}
              rows={14}
            />
          </label>
          <div className="actions">
            <button className="button primary" onClick={saveCompany} disabled={saving}>
              {saving ? "Saving..." : "Save Company"}
            </button>
          </div>
          {error && <p className="error-text">{error}</p>}
        </div>
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
                  <Link
                    key={report.id}
                    href={`/library/${companyId}/reports/${report.id}`}
                    className="report-row"
                  >
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
        </div>
      </section>
    </>
  );
}
