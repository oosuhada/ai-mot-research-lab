"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createComparisonSet, searchPapers, updateComparisonCell } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

export async function createComparisonFromTopic(formData: FormData) {
  assertWorkspaceWritable();
  const query = String(formData.get("query") ?? "").trim();
  if (query.length < 2) {
    redirect("/compare?feedback=invalid-topic");
  }

  const search = await searchPapers(query, "hybrid");
  if (!search || search.items.length < 2) {
    redirect(`/compare?feedback=not-enough-evidence&q=${encodeURIComponent(query)}`);
  }

  const selected = search.items.slice(0, 3);
  let comparison;
  try {
    comparison = await createComparisonSet(
      `Comparison: ${query}`,
      selected.map((paper) => paper.id),
    );
  } catch {
    redirect(`/compare?feedback=error&q=${encodeURIComponent(query)}`);
  }
  redirect(`/compare?id=${comparison.id}&feedback=created`);
}

export async function createComparisonFromIds(formData: FormData) {
  assertWorkspaceWritable();
  const ids = String(formData.get("paper_ids") ?? "")
    .split(/[\s,]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  const unique = [...new Set(ids)];
  if (unique.length < 2 || unique.length > 6) {
    redirect(`/compare?feedback=invalid-selection&papers=${encodeURIComponent(unique.join(","))}`);
  }
  const name = String(formData.get("name") ?? "Selected paper comparison").trim() || "Selected paper comparison";
  let comparison;
  try {
    comparison = await createComparisonSet(name, unique);
  } catch {
    redirect(`/compare?feedback=error&papers=${encodeURIComponent(unique.join(","))}`);
  }
  redirect(`/compare?id=${comparison.id}&feedback=created`);
}

export async function editComparisonCellAction(comparisonId: string, cellId: string, formData: FormData) {
  assertWorkspaceWritable();
  const value = String(formData.get("value_text") ?? "").trim();
  const evidenceChunkId = String(formData.get("evidence_chunk_id") ?? "").trim();
  if (!value) {
    redirect(`/compare?id=${comparisonId}&feedback=invalid-cell`);
  }
  try {
    await updateComparisonCell(comparisonId, cellId, value, evidenceChunkId || undefined);
  } catch {
    redirect(`/compare?id=${comparisonId}&feedback=error`);
  }
  revalidatePath(`/compare?id=${comparisonId}`);
  redirect(`/compare?id=${comparisonId}&feedback=cell-saved`);
}
