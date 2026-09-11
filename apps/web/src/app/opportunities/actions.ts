"use server";

import { redirect } from "next/navigation";

import { createResearchQuestionFromOpportunity } from "@/lib/api";
import { assertWorkspaceWritable } from "@/lib/workspace";

export async function createQuestionFromOpportunityAction(formData: FormData) {
  assertWorkspaceWritable();
  const slug = String(formData.get("slug") ?? "").trim();
  if (!slug) redirect("/opportunities?feedback=invalid-opportunity");
  let result;
  try {
    result = await createResearchQuestionFromOpportunity(slug, 8);
  } catch {
    redirect("/opportunities?feedback=question-error");
  }
  redirect(`/questions/${result.id}?feedback=created-from-opportunity`);
}
