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
  try {
    await updateResearchQuestion(id, {
      motivation: String(formData.get("motivation") ?? "").trim() || null,
      scope_notes: String(formData.get("scope_notes") ?? "").trim() || null,
      importance_notes: String(formData.get("importance_notes") ?? "").trim() || null,
      evidence_status: String(formData.get("evidence_status") ?? "insufficient_evidence"),
      uncertainty_notes: String(formData.get("uncertainty_notes") ?? "").trim() || null,
      status: String(formData.get("status") ?? "exploring"),
    });
  } catch {
    redirect(`${pathFor(id)}?feedback=error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=updated`);
}

export async function linkEntityAction(id: string, kind: "papers" | "saved-searches" | "comparison-sets", formData: FormData) {
  assertWorkspaceWritable();
  const entityId = String(formData.get("entity_id") ?? "").trim();
  if (!entityId) redirect(`${pathFor(id)}?feedback=invalid-link`);
  try {
    await linkResearchQuestionEntity(id, kind, entityId);
  } catch {
    redirect(`${pathFor(id)}?feedback=error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=linked`);
}

export async function addQuestionNoteAction(id: string, formData: FormData) {
  assertWorkspaceWritable();
  const note = String(formData.get("note") ?? "").trim();
  if (!note) redirect(`${pathFor(id)}?feedback=invalid-note`);
  try {
    await addResearchQuestionNote(id, note);
  } catch {
    redirect(`${pathFor(id)}?feedback=error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=note-added`);
}

export async function createQuestionGapAction(id: string, questionText: string) {
  assertWorkspaceWritable();
  let gap;
  try {
    gap = await createGapAnalysis(questionText, id);
  } catch {
    redirect(`${pathFor(id)}?feedback=gap-error`);
  }
  redirect(`/gap-canvas?id=${gap.id}&feedback=created`);
}
