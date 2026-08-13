"use server";

import { redirect } from "next/navigation";

import { importMetadata } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

export async function importMetadataAction(formData: FormData) {
  assertWorkspaceWritable();
  const format = String(formData.get("format") ?? "doi") as "doi" | "bibtex" | "ris" | "csv";
  const content = String(formData.get("content") ?? "").trim();
  if (!content) redirect("/imports?feedback=missing-content");
  let result;
  try {
    result = await importMetadata(format, content);
  } catch {
    redirect("/imports?feedback=error");
  }
  const first = result.paper_ids[0];
  redirect(first ? `/library/${first}?imported=1` : "/imports?feedback=empty");
}
