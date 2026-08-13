import type { Metadata } from "next";

import { Sidebar } from "@/components/Sidebar";
import { getWorkspaceMode } from "@/lib/workspace";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI × MOT Research Lab",
  description: "AI와 기술경영 연구를 위한 근거 기반 논문 인텔리전스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const workspaceMode = getWorkspaceMode();
  return (
    <html lang="en">
      <body>
        <div className="appShell">
          <Sidebar workspaceMode={workspaceMode} />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

