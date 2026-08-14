"use client";

import { useState } from "react";

import type { WorkspaceMode } from "@/lib/workspace";

import { Sidebar } from "./Sidebar";

export function AppShell({
  children,
  workspaceMode,
}: {
  children: React.ReactNode;
  workspaceMode: WorkspaceMode;
}) {
  const [sidebarPinned, setSidebarPinned] = useState(false);

  return (
    <div className={`appShell${sidebarPinned ? " appShellSidebarPinned" : ""}`}>
      <Sidebar
        desktopOpen={sidebarPinned}
        onDesktopOpenChange={setSidebarPinned}
        workspaceMode={workspaceMode}
      />
      <main className="main">{children}</main>
    </div>
  );
}
