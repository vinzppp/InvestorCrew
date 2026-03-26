import "./globals.css";

import { PropsWithChildren } from "react";

import { AppShell } from "@/components/app-shell";

export const metadata = {
  title: "InvestorCrew",
  description: "Local-first UI for investment research runs"
};

export default function RootLayout({ children }: PropsWithChildren) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
