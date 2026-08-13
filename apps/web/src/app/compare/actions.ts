"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createComparisonSet, searchPapers, updateComparisonCell } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

export async function createComparisonFromTopic(formData: FormData) {
  assertWorkspaceWritable();
  const query = String(formData.get("query") ?? "").trim();
  if (query.length < 2) {
    throw new Error("Enter a comparison topic with at least two characters.");
  }

  const search = await searchPapers(query, "hybrid");
  if (!search || search.items.length < 2) {
    throw new Error("At least two retrieved papers are required for comparison.");
  }

  const selected = search.items.slice(0, 3);
  const comparison = await createComparisonSet(
    `Comparison: ${query}`,
    selected.map((paper) => paper.id),
  );
  redirect(`/compare?id=${comparison.id}`);
}

export async function createComparisonFromIds(formData: FormData) {
  assertWorkspaceWritable();
  const ids = String(formData.get("paper_ids") ?? "")
    .split(/[\s,]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  const unique = [...new Set(ids)];
  if (unique.length < 2 || unique.length > 6) throw new Error("Select between 2 and 6 unique paper IDs.");
  const name = String(formData.get("name") ?? "Selected paper comparison").trim() || "Selected paper comparison";
  const comparison = await createComparisonSet(name, unique);
  redirect(`/compare?id=${comparison.id}`);
}

export async function editComparisonCellAction(comparisonId: string, cellId: string, formData: FormData) {
  assertWorkspaceWritable();
  const value = String(formData.get("value_text") ?? "").trim();
  const evidenceChunkId = String(formData.get("evidence_chunk_id") ?? "").trim();
  if (!value) return;
  await updateComparisonCell(comparisonId, cellId, value, evidenceChunkId || undefined);
  revalidatePath(`/compare?id=${comparisonId}`);
}
