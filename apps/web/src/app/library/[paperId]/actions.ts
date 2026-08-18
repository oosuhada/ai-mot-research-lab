"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  addPaperNote,
  addPaperTag,
  deletePaperNote,
  deletePaperTag,
  persistPaperResearchCard,
  setPaperReading,
  updatePaperResearchCard,
  uploadPrivatePdf,
} from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

function pathFor(paperId: string) {
  return `/library/${paperId}`;
}

function feedbackPath(paperId: string, feedback: string) {
  return `${pathFor(paperId)}?feedback=${encodeURIComponent(feedback)}`;
}

export async function updateReadingAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const value = String(formData.get("status") ?? "unread");
  const allowed = new Set(["unread", "skimming", "reading", "read", "archived"]);
  const rawPriority = Number(formData.get("priority") ?? 0);
  if (!allowed.has(value) || !Number.isFinite(rawPriority)) {
    redirect(feedbackPath(paperId, "invalid-reading"));
  }
  const priority = Math.max(0, Math.min(100, rawPriority));
  try {
    await setPaperReading(
      paperId,
      value as "unread" | "skimming" | "reading" | "read" | "archived",
      priority,
    );
  } catch {
    redirect(feedbackPath(paperId, "error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "reading-saved"));
}

export async function addTagAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const name = String(formData.get("name") ?? "").trim();
  if (!name) redirect(feedbackPath(paperId, "invalid-tag"));
  try {
    await addPaperTag(paperId, name);
  } catch {
    redirect(feedbackPath(paperId, "error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "tag-added"));
}

export async function removeTagAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const name = String(formData.get("name") ?? "").trim();
  if (!name) redirect(feedbackPath(paperId, "invalid-tag"));
  try {
    await deletePaperTag(paperId, name);
  } catch {
    redirect(feedbackPath(paperId, "error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "tag-removed"));
}

export async function addNoteAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const note = String(formData.get("note") ?? "").trim();
  const locator = String(formData.get("source_locator") ?? "").trim();
  if (!note) redirect(feedbackPath(paperId, "invalid-note"));
  try {
    await addPaperNote(paperId, note, locator || null);
  } catch {
    redirect(feedbackPath(paperId, "error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "note-added"));
}

export async function removeNoteAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const noteId = String(formData.get("note_id") ?? "").trim();
  if (!noteId) redirect(feedbackPath(paperId, "invalid-note"));
  try {
    await deletePaperNote(noteId);
  } catch {
    redirect(feedbackPath(paperId, "error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "note-removed"));
}

export async function uploadPdfAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const file = formData.get("file");
  const confirmed = formData.get("rights_confirmed") === "on";
  if (!(file instanceof File) || file.size === 0) {
    redirect(feedbackPath(paperId, "missing-pdf"));
  }
  if (!confirmed) {
    redirect(feedbackPath(paperId, "rights-required"));
  }
  try {
    await uploadPrivatePdf(paperId, file);
  } catch {
    redirect(feedbackPath(paperId, "pdf-error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "pdf-uploaded"));
}

const researchCardFields = [
  "one_line_summary",
  "research_question",
  "theoretical_lens",
  "unit_of_analysis",
  "context_industry_country",
  "dataset_and_sample",
  "methodology",
  "analysis_technique",
  "variables_or_constructs",
  "findings",
  "limitations",
  "claimed_contribution",
  "future_research",
] as const;

export async function startResearchCardAction(paperId: string) {
  assertWorkspaceWritable();
  try {
    await persistPaperResearchCard(paperId);
  } catch {
    redirect(feedbackPath(paperId, "research-card-error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, "research-card-started"));
}

export async function updateResearchCardAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const fields = Object.fromEntries(
    researchCardFields.map((field) => [
      field,
      {
        value_text: String(formData.get(`field_${field}`) ?? "").trim() || null,
        source_locator: String(formData.get(`locator_${field}`) ?? "").trim() || null,
      },
    ]),
  );
  const status = String(formData.get("card_status") ?? "in_review");
  if (!new Set(["candidate", "in_review", "reviewed"]).has(status)) {
    redirect(feedbackPath(paperId, "research-card-error"));
  }
  try {
    await updatePaperResearchCard(paperId, {
      fields,
      important_quotes: String(formData.get("important_quotes") ?? "").trim() || null,
      my_interpretation: String(formData.get("my_interpretation") ?? "").trim() || null,
      questions_raised: String(formData.get("questions_raised") ?? "").trim() || null,
      review_notes: String(formData.get("review_notes") ?? "").trim() || null,
      status,
    });
  } catch {
    redirect(feedbackPath(paperId, "research-card-error"));
  }
  revalidatePath(pathFor(paperId));
  redirect(feedbackPath(paperId, status === "reviewed" ? "research-card-reviewed" : "research-card-saved"));
}
