import type { Metadata } from "next";

import { ResearchContextBar, ResearchContextProvider } from "@/components/ResearchContext";
import { LocalePreferenceProvider } from "@/components/LocalePreference";
import { Sidebar } from "@/components/Sidebar";
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
            <div className="appShell">
              <Sidebar workspaceMode={workspaceMode} />
              <main className="main">
                <ResearchContextBar questions={questions} />
                {children}
              </main>
            </div>
          </ResearchContextProvider>
        </LocalePreferenceProvider>
      </body>
    </html>
  );
}
