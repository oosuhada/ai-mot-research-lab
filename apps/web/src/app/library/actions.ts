"use server";

import { revalidatePath } from "next/cache";

import { saveSearch } from "@/lib/api";

export async function saveSearchAction(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  const query = String(formData.get("q") ?? "").trim();
  if (!name || !query) return;
  const filters: Record<string, string> = {};
  for (const key of [
    "mode", "scope", "sort", "year_from", "year_to", "axis", "methodology", "venue", "author",
    "tag", "reading_status", "is_oa",
  ]) {
    const value = String(formData.get(key) ?? "").trim();
    if (value) filters[key] = value;
  }
  await saveSearch(name, query, filters);
  revalidatePath("/library");
}
