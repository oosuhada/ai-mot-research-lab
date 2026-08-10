"use server";

import { redirect } from "next/navigation";

import { createComparisonSet, searchPapers } from "@/lib/api";

export async function createComparisonFromTopic(formData: FormData) {
  const query = String(formData.get("query") ?? "").trim();
  if (query.length < 2) {
    throw new Error("Enter a comparison topic with at least two characters.");
  }

  const search = await searchPapers(query, "hybrid");
  if (!search || search.items.length < 2) {
    throw new Error("At least two retrieved papers are required for comparison.");
  }

  const selected = search.items.slice(0, 3);
  const comparison = await createComparisonSet(
    `Comparison: ${query}`,
    selected.map((paper) => paper.id),
  );
  redirect(`/compare?id=${comparison.id}`);
}
