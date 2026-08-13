"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  addResearchQuestionNote,
  createGapAnalysis,
  linkResearchQuestionEntity,
  updateResearchQuestion,
} from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

const pathFor = (id: string) => `/questions/${id}`;

export async function updateQuestionAction(id: string, formData: FormData) {
  assertWorkspaceWritable();
  await updateResearchQuestion(id, {
    motivation: String(formData.get("motivation") ?? "").trim() || null,
    scope_notes: String(formData.get("scope_notes") ?? "").trim() || null,
    importance_notes: String(formData.get("importance_notes") ?? "").trim() || null,
    evidence_status: String(formData.get("evidence_status") ?? "insufficient_evidence"),
    uncertainty_notes: String(formData.get("uncertainty_notes") ?? "").trim() || null,
    status: String(formData.get("status") ?? "exploring"),
  });
  revalidatePath(pathFor(id));
}

export async function linkEntityAction(id: string, kind: "papers" | "saved-searches" | "comparison-sets", formData: FormData) {
  assertWorkspaceWritable();
  const entityId = String(formData.get("entity_id") ?? "").trim();
  if (!entityId) return;
  await linkResearchQuestionEntity(id, kind, entityId);
  revalidatePath(pathFor(id));
}

export async function addQuestionNoteAction(id: string, formData: FormData) {
  assertWorkspaceWritable();
  const note = String(formData.get("note") ?? "").trim();
  if (!note) return;
  await addResearchQuestionNote(id, note);
  revalidatePath(pathFor(id));
}

export async function createQuestionGapAction(id: string, questionText: string) {
  assertWorkspaceWritable();
  const gap = await createGapAnalysis(questionText, id);
  redirect(`/gap-canvas?id=${gap.id}`);
}
