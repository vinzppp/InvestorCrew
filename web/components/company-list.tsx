"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listCompanies } from "@/lib/api";
import { CompanySummary } from "@/lib/types";

export function CompanyList() {
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<CompanySummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listCompanies(search)
      .then(setItems)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load companies"));
  }, [search]);

  return (
    <section className="panel panel-large">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Library</p>
          <h2>Company workspaces and report history</h2>
        </div>
      </div>
      <label className="field">
        <span>Search companies</span>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by ticker or company name"
        />
      </label>
      {error && <p className="error-text">{error}</p>}
      <div className="card-grid">
        {items.map((company) => (
          <Link key={company.ticker} href={`/library/${company.ticker}`} className="company-card">
            <div className="company-card-head">
              <span className="ticker-chip">{company.ticker}</span>
              <span className="meta-value">{company.report_count} reports</span>
            </div>
            <h3>{company.name}</h3>
            <p>{company.industry}</p>
            <div className="company-card-foot">
              <span>{company.archetype}</span>
              <span>{company.last_report_at ? company.last_report_at.slice(0, 10) : "No reports yet"}</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
