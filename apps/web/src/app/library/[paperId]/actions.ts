"use server";

import { revalidatePath } from "next/cache";

import {
  addPaperNote,
  addPaperTag,
  deletePaperNote,
  deletePaperTag,
  setPaperReading,
  uploadPrivatePdf,
} from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

function pathFor(paperId: string) {
  return `/library/${paperId}`;
}

export async function updateReadingAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const value = String(formData.get("status") ?? "unread");
  const allowed = new Set(["unread", "skimming", "reading", "read", "archived"]);
  if (!allowed.has(value)) throw new Error("Invalid reading status");
  const priority = Math.max(0, Math.min(100, Number(formData.get("priority") ?? 0)));
  await setPaperReading(
    paperId,
    value as "unread" | "skimming" | "reading" | "read" | "archived",
    priority,
  );
  revalidatePath(pathFor(paperId));
}

export async function addTagAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return;
  await addPaperTag(paperId, name);
  revalidatePath(pathFor(paperId));
}

export async function removeTagAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return;
  await deletePaperTag(paperId, name);
  revalidatePath(pathFor(paperId));
}

export async function addNoteAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const note = String(formData.get("note") ?? "").trim();
  const locator = String(formData.get("source_locator") ?? "").trim();
  if (!note) return;
  await addPaperNote(paperId, note, locator || null);
  revalidatePath(pathFor(paperId));
}

export async function removeNoteAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const noteId = String(formData.get("note_id") ?? "").trim();
  if (!noteId) return;
  await deletePaperNote(noteId);
  revalidatePath(pathFor(paperId));
}

export async function uploadPdfAction(paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const file = formData.get("file");
  const confirmed = formData.get("rights_confirmed") === "on";
  if (!(file instanceof File) || file.size === 0) return;
  if (!confirmed) throw new Error("Rights confirmation is required for private PDF processing");
  await uploadPrivatePdf(paperId, file);
  revalidatePath(pathFor(paperId));
}
