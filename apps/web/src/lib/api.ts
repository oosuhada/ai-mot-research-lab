export type LandscapeAxis = {
  slug: string;
  display_name: string;
  paper_count: number;
};

export type LandscapeYear = {
  year: number;
  paper_count: number;
};

export type Landscape = {
  total_papers: number;
  axes: LandscapeAxis[];
  years: LandscapeYear[];
};

export type SearchItem = {
  id: string;
  doi: string | null;
  openalex_id: string | null;
  title: string;
  abstract: string | null;
  publication_date: string | null;
  publication_year: number | null;
  work_type: string | null;
  oa_status: string | null;
  is_oa: boolean;
  primary_url: string | null;
  pdf_url: string | null;
  license: string | null;
  lexical_rank: number | null;
  semantic_rank: number | null;
  fused_score: number;
};

export type SearchResponse = {
  query: string;
  mode: "lexical" | "vector" | "hybrid";
  total: number;
  items: SearchItem[];
};

export type PaperTopic = {
  slug: string;
  display_name: string;
  kind: string;
  assignment_source: string;
};

export type PaperDetail = SearchItem & {
  language: string | null;
  publisher: string | null;
  retraction_status: string;
  correction_status: string;
  primary_source: string;
  source_record_id: string;
  retrieved_at: string;
  provenance: Record<string, unknown>;
  venue: { id: string; name: string; publisher: string | null; venue_type: string | null } | null;
  authors: Array<{ id: string; display_name: string; openalex_id: string | null; orcid: string | null }>;
  topics: PaperTopic[];
  reading: { status: "unread" | "skimming" | "reading" | "read" | "archived"; priority: number } | null;
  notes: Array<{ id: string; note_markdown: string; source_locator: string | null; created_at: string; updated_at: string }>;
  tags: Array<{ id: string; name: string }>;
  latest_citation_count: number | null;
  latest_citation_snapshot_at: string | null;
};

export type EvidenceLink = {
  paper_id: string;
  paper_title: string;
  doi: string | null;
  primary_url: string | null;
  relation: string;
  source_locator: string | null;
};

export type ComparisonPaper = {
  id: string;
  title: string;
  doi: string | null;
  publication_year: number | null;
};

export type ComparisonCell = {
  id: string;
  paper_id: string;
  field_name: string;
  value_text: string | null;
  support_status: string;
  claim_kind: string;
  evidence: EvidenceLink[];
};

export type ComparisonSet = {
  id: string;
  name: string;
  description: string | null;
  papers: ComparisonPaper[];
  cells: ComparisonCell[];
};

export type GapEvidenceClaim = {
  id: string;
  claim_text: string;
  claim_kind: string;
  support_status: string;
  evidence: EvidenceLink[];
};

export type GapAnalysis = {
  id: string;
  research_question_id: string;
  research_question: string;
  status: string;
  search_strategy: string;
  inclusion_criteria: string;
  exclusion_criteria: string;
  research_clusters: string | null;
  agreements: string | null;
  conflicts: string | null;
  under_studied_contexts: string | null;
  gap_candidates: string | null;
  falsifiability_notes: string | null;
  follow_up_questions: string | null;
  theoretical_lenses: string | null;
  candidate_data_methods: string | null;
  evidence_claims: GapEvidenceClaim[];
};

export type ChatCitation = {
  index: number;
  paper_id: string;
  paper_title: string;
  publication_year: number | null;
  doi: string | null;
  primary_url: string | null;
  source_locator: string;
  excerpt: string;
};

export type ChatParagraph = {
  text: string;
  claim_kind: string;
  support_status: string;
  citation_indexes: number[];
};

export type ChatResponse = {
  question: string;
  scope_type: string;
  provider: string;
  paragraphs: ChatParagraph[];
  citations: ChatCitation[];
  structural_unsupported_claim_rate: number;
  limitations: string[];
};

export const API_BASE_URL =
  process.env.INTERNAL_API_BASE_URL?.replace(/\/$/, "") ??
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export async function getLandscape(): Promise<Landscape | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/landscape`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as Landscape;
  } catch {
    return null;
  }
}

export async function searchPapers(
  query: string,
  mode: "lexical" | "vector" | "hybrid" = "hybrid",
): Promise<SearchResponse | null> {
  if (!query.trim()) {
    return null;
  }

  try {
    const params = new URLSearchParams({ q: query, mode, limit: "20" });
    const response = await fetch(`${API_BASE_URL}/api/v1/search?${params.toString()}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as SearchResponse;
  } catch {
    return null;
  }
}

export async function getPaper(id: string): Promise<PaperDetail | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/papers/${id}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as PaperDetail;
  } catch {
    return null;
  }
}

async function mutatePaper(path: string, init: RequestInit): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Paper mutation failed with ${response.status}`);
  }
}

export async function setPaperReading(
  id: string,
  status: "unread" | "skimming" | "reading" | "read" | "archived",
  priority: number,
): Promise<void> {
  await mutatePaper(`/api/v1/papers/${id}/reading`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, priority }),
  });
}

export async function addPaperTag(id: string, name: string): Promise<void> {
  await mutatePaper(`/api/v1/papers/${id}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function deletePaperTag(id: string, name: string): Promise<void> {
  await mutatePaper(`/api/v1/papers/${id}/tags/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export async function addPaperNote(id: string, note: string, sourceLocator: string | null): Promise<void> {
  await mutatePaper(`/api/v1/papers/${id}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note_markdown: note, source_locator: sourceLocator }),
  });
}

export async function deletePaperNote(noteId: string): Promise<void> {
  await mutatePaper(`/api/v1/notes/${noteId}`, { method: "DELETE" });
}

export async function createComparisonSet(
  name: string,
  paperIds: string[],
): Promise<ComparisonSet> {
  const response = await fetch(`${API_BASE_URL}/api/v1/comparison-sets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, paper_ids: paperIds }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Comparison API failed with ${response.status}`);
  }
  return (await response.json()) as ComparisonSet;
}

export async function getComparisonSet(id: string): Promise<ComparisonSet | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/comparison-sets/${id}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as ComparisonSet;
  } catch {
    return null;
  }
}

export async function createGapAnalysis(topic: string): Promise<GapAnalysis> {
  const response = await fetch(`${API_BASE_URL}/api/v1/gap-analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, retrieval_limit: 20 }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Gap analysis API failed with ${response.status}`);
  }
  return (await response.json()) as GapAnalysis;
}

export async function getGapAnalysis(id: string): Promise<GapAnalysis | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/gap-analyses/${id}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as GapAnalysis;
  } catch {
    return null;
  }
}

export async function updateGapAnalysis(
  id: string,
  fields: Record<string, string>,
): Promise<GapAnalysis> {
  const response = await fetch(`${API_BASE_URL}/api/v1/gap-analyses/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Gap analysis update failed with ${response.status}`);
  }
  return (await response.json()) as GapAnalysis;
}

export async function askChat(
  question: string,
  scopeType: "corpus" | "papers" | "comparison_set" = "corpus",
  scopeIds: string[] = [],
): Promise<ChatResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        scope_type: scopeType,
        scope_ids: scopeIds,
        max_papers: 5,
      }),
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as ChatResponse;
  } catch {
    return null;
  }
}

