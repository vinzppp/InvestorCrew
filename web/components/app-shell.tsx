"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PropsWithChildren } from "react";

const tabs = [
  { href: "/ask", label: "Ask" },
  { href: "/library", label: "Library" },
  { href: "/configure", label: "Configure" }
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  return (
    <div className="app-frame">
      <header className="hero">
        <div>
          <p className="eyebrow">InvestorCrew</p>
          <h1>Investment research cockpit</h1>
          <p className="hero-copy">
            Ask a question, inspect company report history, and tune the crew’s prompts and settings in one place.
          </p>
        </div>
        <nav className="tab-bar" aria-label="Primary">
          {tabs.map((tab) => {
            const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
            return (
              <Link key={tab.href} className={active ? "tab active" : "tab"} href={tab.href}>
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="page-grid">{children}</main>
    </div>
  );
}
