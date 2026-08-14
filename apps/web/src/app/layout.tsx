import type { Metadata } from "next";

import { AppShell } from "@/components/AppShell";
import { ResearchContextBar, ResearchContextProvider } from "@/components/ResearchContext";
import { LocalePreferenceProvider } from "@/components/LocalePreference";
import { listResearchQuestions } from "@/lib/api";
import { getWorkspaceMode } from "@/lib/workspace";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI × MOT Research Lab",
  description: "AI와 기술경영 연구를 위한 근거 기반 논문 인텔리전스",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const workspaceMode = getWorkspaceMode();
  const questions = await listResearchQuestions();
  return (
    <html lang="en">
      <body>
        <LocalePreferenceProvider>
          <ResearchContextProvider questions={questions}>
            <AppShell workspaceMode={workspaceMode}>
              <ResearchContextBar questions={questions} />
              {children}
            </AppShell>
          </ResearchContextProvider>
        </LocalePreferenceProvider>
      </body>
    </html>
  );
}
