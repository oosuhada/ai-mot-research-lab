"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  addResearchQuestionNote,
  createGapAnalysis,
  createResearchDirection,
  linkResearchQuestionEntity,
  saveResearchDesign,
  updateResearchDirection,
  updateResearchQuestion,
  updateResearchQuestionPaper,
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

export async function updateLinkedPaperAction(id: string, paperId: string, formData: FormData) {
  assertWorkspaceWritable();
  const literatureTier = String(formData.get("literature_tier") ?? "candidate");
  const allowedTiers = new Set(["candidate", "reading", "core", "foundation", "excluded"]);
  if (!allowedTiers.has(literatureTier)) redirect(`${pathFor(id)}?feedback=paper-workflow-error`);
  try {
    await updateResearchQuestionPaper(id, paperId, {
      relation: String(formData.get("relation") ?? "relevant").trim() || "relevant",
      literature_tier: literatureTier,
      relationship_note: String(formData.get("relationship_note") ?? "").trim() || null,
    });
  } catch {
    redirect(`${pathFor(id)}?feedback=paper-workflow-error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=paper-workflow-saved`);
}

function dimensionScores(formData: FormData): Record<string, number> {
  const keys = ["novelty", "theory_fit", "data_feasibility", "method_feasibility", "scope_fit", "personal_interest"];
  return Object.fromEntries(
    keys.map((key) => {
      const raw = Number(formData.get(key) ?? 3);
      return [key, Math.max(1, Math.min(5, Number.isFinite(raw) ? Math.round(raw) : 3))];
    }),
  );
}

export async function createDirectionAction(id: string, formData: FormData) {
  assertWorkspaceWritable();
  const title = String(formData.get("title") ?? "").trim();
  if (title.length < 3) redirect(`${pathFor(id)}?feedback=direction-error`);
  try {
    await createResearchDirection(id, {
      title,
      rationale: String(formData.get("rationale") ?? "").trim() || null,
      status: String(formData.get("status") ?? "candidate"),
      evidence_status: String(formData.get("evidence_status") ?? "insufficient_evidence"),
      dimensions: dimensionScores(formData),
      evidence_for: String(formData.get("evidence_for") ?? "").trim() || null,
      evidence_against: String(formData.get("evidence_against") ?? "").trim() || null,
      next_test: String(formData.get("next_test") ?? "").trim() || null,
      theory_note: String(formData.get("theory_note") ?? "").trim() || null,
      data_note: String(formData.get("data_note") ?? "").trim() || null,
      method_note: String(formData.get("method_note") ?? "").trim() || null,
    });
  } catch {
    redirect(`${pathFor(id)}?feedback=direction-error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=direction-created`);
}

export async function createDirectionFromGapAction(id: string, gapCandidate: string) {
  assertWorkspaceWritable();
  try {
    await createResearchDirection(id, {
      title: gapCandidate.slice(0, 500),
      rationale: "Promoted from the current Gap Canvas candidate. Test this direction before treating it as a gap.",
      status: "testing",
      evidence_status: "insufficient_evidence",
      dimensions: {
        novelty: 3,
        theory_fit: 3,
        data_feasibility: 3,
        method_feasibility: 3,
        scope_fit: 3,
        personal_interest: 3,
      },
      next_test: "Broaden search terms, inspect citation neighbors, and look for direct counter-evidence.",
    });
  } catch {
    redirect(`${pathFor(id)}?feedback=direction-error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=direction-created`);
}

export async function updateDirectionAction(id: string, directionId: string, formData: FormData) {
  assertWorkspaceWritable();
  try {
    await updateResearchDirection(id, directionId, {
      title: String(formData.get("title") ?? "").trim(),
      rationale: String(formData.get("rationale") ?? "").trim() || null,
      status: String(formData.get("status") ?? "candidate"),
      evidence_status: String(formData.get("evidence_status") ?? "insufficient_evidence"),
      dimensions: dimensionScores(formData),
      evidence_for: String(formData.get("evidence_for") ?? "").trim() || null,
      evidence_against: String(formData.get("evidence_against") ?? "").trim() || null,
      next_test: String(formData.get("next_test") ?? "").trim() || null,
      theory_note: String(formData.get("theory_note") ?? "").trim() || null,
      data_note: String(formData.get("data_note") ?? "").trim() || null,
      method_note: String(formData.get("method_note") ?? "").trim() || null,
    });
  } catch {
    redirect(`${pathFor(id)}?feedback=direction-error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=direction-saved`);
}

export async function saveResearchDesignAction(id: string, formData: FormData) {
  assertWorkspaceWritable();
  const fields = [
    "theoretical_framework",
    "focal_constructs",
    "independent_variables",
    "dependent_variables",
    "mediators",
    "moderators",
    "unit_of_analysis",
    "context_population",
    "data_sources",
    "sampling_plan",
    "methodology",
    "analysis_plan",
    "hypotheses",
    "feasibility_notes",
    "ethics_constraints",
    "expected_contribution",
  ];
  const payload = Object.fromEntries(
    fields.map((field) => [field, String(formData.get(field) ?? "").trim() || null]),
  );
  try {
    await saveResearchDesign(id, {
      ...payload,
      selected_direction_id: String(formData.get("selected_direction_id") ?? "").trim() || null,
      status: String(formData.get("status") ?? "draft"),
    });
  } catch {
    redirect(`${pathFor(id)}?feedback=design-error`);
  }
  revalidatePath(pathFor(id));
  redirect(`${pathFor(id)}?feedback=design-saved`);
}
