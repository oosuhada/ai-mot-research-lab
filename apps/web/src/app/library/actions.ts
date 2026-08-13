"use server";

import { revalidatePath } from "next/cache";

import { linkResearchQuestionEntity, saveSearch } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

export async function saveSearchAction(formData: FormData) {
  assertWorkspaceWritable();
  const name = String(formData.get("name") ?? "").trim();
  const query = String(formData.get("q") ?? "").trim();
  if (!name || !query) return;
  const filters: Record<string, string> = {};
  for (const key of [
    "mode", "scope", "sort", "year_from", "year_to", "axis", "methodology", "venue", "author",
    "tag", "reading_status", "is_oa",
  ]) {
    const value = String(formData.get(key) ?? "").trim();
    if (value) filters[key] = value;
  }
  await saveSearch(name, query, filters);
  revalidatePath("/library");
}

export async function linkSelectedPapersAction(formData: FormData) {
  assertWorkspaceWritable();
  const questionId = String(formData.get("question_id") ?? "").trim();
  const paperIds = String(formData.get("paper_ids") ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!questionId || !paperIds.length) return;
  for (const paperId of [...new Set(paperIds)]) {
    await linkResearchQuestionEntity(questionId, "papers", paperId);
  }
  revalidatePath(`/questions/${questionId}`);
}
