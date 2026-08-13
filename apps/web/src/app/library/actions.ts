"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { linkResearchQuestionEntity, saveSearch } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

function feedbackHref(returnTo: string, feedback: "saved" | "linked" | "error") {
  const fallback = new URL("http://research.local/library");
  let target = fallback;
  try {
    const parsed = new URL(returnTo, fallback);
    if (parsed.pathname === "/library") target = parsed;
  } catch {
    target = fallback;
  }
  target.searchParams.set("feedback", feedback);
  return `${target.pathname}?${target.searchParams.toString()}`;
}

export async function saveSearchAction(formData: FormData) {
  assertWorkspaceWritable();
  const name = String(formData.get("name") ?? "").trim();
  const query = String(formData.get("q") ?? "").trim();
  const returnTo = String(formData.get("return_to") ?? "/library");
  if (!name || !query) return;
  const filters: Record<string, string> = {};
  for (const key of [
    "mode", "scope", "sort", "year_from", "year_to", "axis", "methodology", "venue", "author",
    "tag", "reading_status", "is_oa",
  ]) {
    const value = String(formData.get(key) ?? "").trim();
    if (value) filters[key] = value;
  }
  let feedback: "saved" | "error" = "saved";
  try {
    await saveSearch(name, query, filters);
    revalidatePath("/library");
  } catch {
    feedback = "error";
  }
  redirect(feedbackHref(returnTo, feedback));
}

export async function linkSelectedPapersAction(formData: FormData) {
  assertWorkspaceWritable();
  const questionId = String(formData.get("question_id") ?? "").trim();
  const returnTo = String(formData.get("return_to") ?? "/library");
  const paperIds = String(formData.get("paper_ids") ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!questionId || !paperIds.length) return;
  let feedback: "linked" | "error" = "linked";
  try {
    for (const paperId of [...new Set(paperIds)]) {
      await linkResearchQuestionEntity(questionId, "papers", paperId);
    }
    revalidatePath(`/questions/${questionId}`);
  } catch {
    feedback = "error";
  }
  redirect(feedbackHref(returnTo, feedback));
}
