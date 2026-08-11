"use server";

import { redirect } from "next/navigation";

import { createResearchQuestion } from "@/lib/api";

export async function createQuestionAction(formData: FormData) {
  const questionText = String(formData.get("question_text") ?? "").trim();
  if (!questionText) return;
  const result = await createResearchQuestion({
    title: String(formData.get("title") ?? questionText).trim() || questionText,
    question_text: questionText,
    motivation: String(formData.get("motivation") ?? "").trim() || null,
    importance_notes: String(formData.get("importance_notes") ?? "").trim() || null,
    uncertainty_notes: String(formData.get("uncertainty_notes") ?? "").trim() || null,
    evidence_status: "insufficient_evidence",
  });
  redirect(`/questions/${result.id}`);
}
