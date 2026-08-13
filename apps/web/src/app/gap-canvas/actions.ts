"use server";

import { redirect } from "next/navigation";

import { createGapAnalysis, updateGapAnalysis } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

export async function createGapCanvas(formData: FormData) {
  assertWorkspaceWritable();
  const topic = String(formData.get("topic") ?? "").trim();
  if (topic.length < 3) {
    redirect("/gap-canvas?feedback=invalid-topic");
  }
  let analysis;
  try {
    analysis = await createGapAnalysis(topic);
  } catch {
    redirect("/gap-canvas?feedback=error");
  }
  redirect(`/gap-canvas?id=${analysis.id}&feedback=created`);
}

export async function challengeGapCanvas(
  analysisId: string,
  researchQuestionId: string,
  searchQuery: string,
  formData: FormData,
) {
  assertWorkspaceWritable();
  void formData;
  const query = searchQuery.trim();
  if (!query) {
    redirect(`/gap-canvas?id=${analysisId}&feedback=invalid-query`);
  }
  let analysis;
  try {
    analysis = await createGapAnalysis(query, researchQuestionId, 40);
  } catch {
    redirect(`/gap-canvas?id=${analysisId}&feedback=error`);
  }
  redirect(`/gap-canvas?id=${analysis.id}&feedback=challenged`);
}

export async function editGapCanvas(analysisId: string, formData: FormData) {
  assertWorkspaceWritable();
  const editableFields = [
    "research_clusters",
    "agreements",
    "conflicts",
    "under_studied_contexts",
    "gap_candidates",
    "falsifiability_notes",
    "follow_up_questions",
    "theoretical_lenses",
    "candidate_data_methods",
  ];
  const updates: Record<string, string> = {};
  for (const field of editableFields) {
    const value = formData.get(field);
    if (typeof value === "string") {
      updates[field] = value;
    }
  }
  try {
    await updateGapAnalysis(analysisId, updates);
  } catch {
    redirect(`/gap-canvas?id=${analysisId}&feedback=error`);
  }
  redirect(`/gap-canvas?id=${analysisId}&feedback=updated`);
}
