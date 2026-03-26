"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { StructuredValue } from "@/components/data-view";
import { createRun, getRun, getRunEvents } from "@/lib/api";
import { ReportEvent, RunRecord } from "@/lib/types";

function statusTone(status: string): string {
  if (status === "COMPLETED") return "good";
  if (status === "FAILED") return "bad";
  if (status === "RUNNING") return "warn";
  return "neutral";
}

export function AskRunner() {
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<ReportEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);

  const reportHref = useMemo(() => {
    if (!run?.company_ticker) return null;
    return `/library/${run.company_ticker}/reports/${run.id}`;
  }, [run]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
      }
    };
  }, []);

  async function refresh(runId: string) {
    const [nextRun, nextEvents] = await Promise.all([getRun(runId), getRunEvents(runId)]);
    setRun(nextRun);
    setEvents(nextEvents);
    if (nextRun.status === "COMPLETED" || nextRun.status === "FAILED") {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setEvents([]);
    try {
      const created = await createRun(question, context);
      setRun(created);
      await refresh(created.id);
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
      }
      pollingRef.current = window.setInterval(() => {
        void refresh(created.id);
      }, 1500);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Run failed");
    }
  }

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">New Question</p>
            <h2>Kick off a live InvestorCrew run</h2>
          </div>
          {run && <span className={`status-pill ${statusTone(run.status)}`}>{run.status}</span>}
        </div>
        <form className="stack" onSubmit={onSubmit}>
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
            <button className="button primary" type="submit">
              Start Run
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

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Live Progress</p>
            <h2>Transcript and orchestration events</h2>
          </div>
        </div>
        {run ? (
          <div className="stack">
            <div className="run-meta">
              <div>
                <span className="meta-label">Run ID</span>
                <strong>{run.id}</strong>
              </div>
              <div>
                <span className="meta-label">Company</span>
                <strong>{run.company_name ?? "Pending detection"}</strong>
              </div>
              <div>
                <span className="meta-label">Routing</span>
                <strong>{String(run.classification?.category ?? "Pending")}</strong>
              </div>
            </div>
            <ol className="timeline">
              {events.map((event) => (
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
            {!events.length && <p className="muted">Waiting for the first transcript event.</p>}
          </div>
        ) : (
          <p className="muted">Submit a question to see the run timeline appear here.</p>
        )}
      </section>
    </>
  );
}
