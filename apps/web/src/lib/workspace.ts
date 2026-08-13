export type WorkspaceMode = "public_demo" | "personal";

export function getWorkspaceMode(): WorkspaceMode {
  const configured = process.env.NEXT_PUBLIC_WORKSPACE_MODE;
  if (configured === "personal" || configured === "public_demo") {
    return configured;
  }
  return process.env.NODE_ENV === "production" ? "public_demo" : "personal";
}

export function isWorkspaceReadOnly(): boolean {
  return getWorkspaceMode() === "public_demo";
}

export function assertWorkspaceWritable(): void {
  if (isWorkspaceReadOnly()) {
    throw new Error("This public portfolio deployment is read-only. Use a personal workspace to make changes.");
  }
}
