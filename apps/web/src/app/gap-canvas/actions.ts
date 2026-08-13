"use server";

import { redirect } from "next/navigation";

import { createGapAnalysis, updateGapAnalysis } from "@/lib/api";

export async function createGapCanvas(formData: FormData) {
  const topic = String(formData.get("topic") ?? "").trim();
  if (topic.length < 3) {
    throw new Error("Enter a research topic with at least three characters.");
  }
  const analysis = await createGapAnalysis(topic);
  redirect(`/gap-canvas?id=${analysis.id}`);
}

export async function challengeGapCanvas(
  researchQuestionId: string,
  searchQuery: string,
  formData: FormData,
) {
  void formData;
  const query = searchQuery.trim();
  if (!query) {
    throw new Error("A falsification search query is required.");
  }
  const analysis = await createGapAnalysis(query, researchQuestionId, 40);
  redirect(`/gap-canvas?id=${analysis.id}`);
}

export async function editGapCanvas(analysisId: string, formData: FormData) {
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
  await updateGapAnalysis(analysisId, updates);
  redirect(`/gap-canvas?id=${analysisId}`);
}
