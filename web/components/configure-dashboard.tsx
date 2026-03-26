"use client";

import { useEffect, useState } from "react";

import { listInvestors, listPrompts, listSettings, updateInvestor, updatePrompt, updateSetting } from "@/lib/api";
import { InvestorProfilePayload, PromptTemplate, SettingRecord } from "@/lib/types";

export function ConfigureDashboard() {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [investors, setInvestors] = useState<InvestorProfilePayload[]>([]);
  const [settings, setSettings] = useState<SettingRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [nextPrompts, nextInvestors, nextSettings] = await Promise.all([
      listPrompts(),
      listInvestors(),
      listSettings()
    ]);
    setPrompts(nextPrompts);
    setInvestors(nextInvestors);
    setSettings(nextSettings);
  }

  useEffect(() => {
    void refresh().catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load config"));
  }, []);

  return (
    <>
      <section className="panel panel-large">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Configure</p>
            <h2>Prompt stack and crew settings</h2>
          </div>
        </div>
        {error && <p className="error-text">{error}</p>}
        <div className="stack">
          {prompts.map((prompt) => (
            <PromptEditor key={prompt.key} prompt={prompt} onSaved={refresh} />
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Investors</p>
            <h2>Persona metadata</h2>
          </div>
        </div>
        <div className="stack">
          {investors.map((investor) => (
            <InvestorEditor key={investor.slug} investor={investor} onSaved={refresh} />
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Settings</p>
            <h2>Runtime defaults</h2>
          </div>
        </div>
        <div className="stack">
          {settings.map((setting) => (
            <SettingEditor key={setting.key} setting={setting} onSaved={refresh} />
          ))}
        </div>
      </section>
    </>
  );
}

function PromptEditor({ prompt, onSaved }: { prompt: PromptTemplate; onSaved: () => Promise<void> }) {
  const [content, setContent] = useState(prompt.content);
  const [busy, setBusy] = useState(false);

  return (
    <div className="content-card prompt-card">
      <div className="card-header-inline">
        <div>
          <h3>{prompt.label}</h3>
          <p>{prompt.description}</p>
          <p className="meta-label">{prompt.key}</p>
        </div>
        <button
          className="button subtle"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await updatePrompt(prompt.key, content, prompt.label, prompt.description);
            setBusy(false);
            await onSaved();
          }}
        >
          {busy ? "Saving..." : "Save Prompt"}
        </button>
      </div>
      <textarea
        className="prompt-textarea"
        value={content}
        onChange={(event) => setContent(event.target.value)}
        rows={16}
      />
    </div>
  );
}

function InvestorEditor({
  investor,
  onSaved
}: {
  investor: InvestorProfilePayload;
  onSaved: () => Promise<void>;
}) {
  const [payload, setPayload] = useState<InvestorProfilePayload>(investor);
  const [busy, setBusy] = useState(false);
  return (
    <div className="content-card">
      <div className="card-header-inline">
        <div>
          <h3>{payload.name}</h3>
          <p>{payload.debate_role}</p>
        </div>
        <button
          className="button subtle"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await updateInvestor(payload.slug, payload as unknown as Record<string, unknown>);
            setBusy(false);
            await onSaved();
          }}
        >
          {busy ? "Saving..." : "Save Investor"}
        </button>
      </div>
      <label className="field">
        <span>Philosophy</span>
        <textarea
          value={payload.philosophy}
          onChange={(event) => setPayload({ ...payload, philosophy: event.target.value })}
          rows={5}
        />
      </label>
      <label className="field">
        <span>Preferred Metrics</span>
        <input
          value={payload.preferred_metrics.join(", ")}
          onChange={(event) =>
            setPayload({
              ...payload,
              preferred_metrics: event.target.value.split(",").map((item) => item.trim()).filter(Boolean)
            })
          }
        />
      </label>
    </div>
  );
}

function SettingEditor({ setting, onSaved }: { setting: SettingRecord; onSaved: () => Promise<void> }) {
  const [value, setValue] = useState(JSON.stringify(setting.value));
  const [busy, setBusy] = useState(false);
  return (
    <div className="content-card">
      <div className="card-header-inline">
        <div>
          <h3>{setting.key}</h3>
        </div>
        <button
          className="button subtle"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await updateSetting(setting.key, JSON.parse(value));
            setBusy(false);
            await onSaved();
          }}
        >
          {busy ? "Saving..." : "Save Setting"}
        </button>
      </div>
      <textarea value={value} onChange={(event) => setValue(event.target.value)} rows={4} />
    </div>
  );
}
