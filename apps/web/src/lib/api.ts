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
  methodologies: LandscapeAxis[];
  years: LandscapeYear[];
  top_authors: Array<{ name: string; paper_count: number }>;
  top_institutions: Array<{ name: string; paper_count: number }>;
  top_venues: Array<{ name: string; paper_count: number }>;
  oa_papers: number;
  last_ingestion_at: string | null;
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
  rerank_score: number | null;
  matched_source: string;
  matched_locator: string | null;
  matched_excerpt: string | null;
  citation_count: number;
  reading_priority: number;
};

export type SearchResponse = {
  query: string;
  mode: "lexical" | "vector" | "hybrid";
  semantic_provider: "local_hash" | "fastembed";
  semantic_provider_requested: "auto" | "local_hash" | "fastembed";
  semantic_provider_reason: string;
  reranker: string;
  scope: "metadata" | "abstract" | "full_text" | "all";
  sort: "relevance" | "newest" | "citation_count" | "reading_priority";
  total: number;
  items: SearchItem[];
};

export type SearchOptions = {
  semantic_provider?: "auto" | "local_hash" | "fastembed";
  rerank?: "none" | "fastembed";
  scope?: "metadata" | "abstract" | "full_text" | "all";
  sort?: "relevance" | "newest" | "citation_count" | "reading_priority";
  year_from?: string;
  year_to?: string;
  axis?: string;
  methodology?: string;
  work_type?: string;
  venue?: string;
  author?: string;
  is_oa?: string;
  reading_status?: string;
  tag?: string;
};

export type SavedSearch = {
  id: string;
  name: string;
  query_text: string;
  filters: Record<string, unknown>;
  created_at: string;
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

export type CitationNeighbor = {
  id: string;
  title: string;
  doi: string | null;
  publication_year: number | null;
  primary_url: string | null;
  direction: "backward" | "forward";
  source: string;
  citation_count: number | null;
};

export type CitationSnowball = {
  paper_id: string;
  paper_title: string;
  backward: CitationNeighbor[];
  forward: CitationNeighbor[];
};

export type EvidenceLink = {
  paper_id: string;
  paper_title: string;
  doi: string | null;
  primary_url: string | null;
  publication_year: number | null;
  venue_name: string | null;
  relation: string;
  source_locator: string | null;
  excerpt: string | null;
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
  origin: string;
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
  methodology_distribution: LandscapeAxis[];
  year_distribution: LandscapeYear[];
  evidence_clusters: Array<{
    slug: string;
    display_name: string;
    paper_ids: string[];
  }>;
  citation_neighborhood: {
    seed_paper_count: number;
    backward_edge_count: number;
    forward_edge_count: number;
    unique_candidate_count: number;
    candidates: Array<{
      paper_id: string;
      title: string;
      publication_year: number | null;
      primary_url: string | null;
      direction: "backward" | "forward" | "both";
      linked_seed_count: number;
    }>;
  };
  candidate_gap: {
    hypothesis: string;
    support_status: "insufficient_evidence";
    evidence_for: string[];
    evidence_against: string[];
    falsifiability_note: string;
    next_search_query: string;
    candidate_method: string | null;
  } | null;
  evidence_claims: GapEvidenceClaim[];
};

export type ResearchQuestion = {
  id: string;
  title: string;
  question_text: string;
  motivation: string | null;
  scope_notes: string | null;
  importance_notes: string | null;
  evidence_status: string;
  uncertainty_notes: string | null;
  status: string;
  papers: Array<{ id: string; title: string; doi: string | null; publication_year: number | null; relation: string }>;
  saved_searches: Array<{ id: string; name: string; query_text: string }>;
  comparison_sets: Array<{ id: string; name: string }>;
  gap_analyses: Array<{
    id: string;
    status: string;
    gap_candidates: string | null;
    search_strategy: string;
    created_at: string;
  }>;
  notes: Array<{ id: string; note_markdown: string; created_at: string; updated_at: string }>;
  created_at: string;
  updated_at: string;
};

export type ResearchQuestionRecommendation = {
  id: string;
  title: string;
  doi: string | null;
  publication_year: number | null;
  reasons: string[];
  score: number;
  score_components: Record<string, number>;
  query_rank: number | null;
  backward_seed_count: number;
  forward_seed_count: number;
  reading_status: string | null;
  semantic_provider: string;
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

export const BROWSER_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

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
  options: SearchOptions = {},
): Promise<SearchResponse | null> {
  if (!query.trim()) {
    return null;
  }

  try {
    const params = new URLSearchParams({
      q: query,
      mode,
      semantic_provider: options.semantic_provider ?? "auto",
      rerank: options.rerank ?? "none",
      scope: options.scope ?? "all",
      sort: options.sort ?? "relevance",
      limit: "20",
    });
    for (const [key, value] of Object.entries(options)) {
      if (
        value &&
        key !== "scope" &&
        key !== "sort" &&
        key !== "semantic_provider" &&
        key !== "rerank"
      ) params.set(key, value);
    }
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

export async function listSavedSearches(): Promise<SavedSearch[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/saved-searches`, { cache: "no-store" });
    return response.ok ? await response.json() as SavedSearch[] : [];
  } catch {
    return [];
  }
}

export async function saveSearch(name: string, queryText: string, filters: Record<string, unknown>): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/saved-searches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, query_text: queryText, filters }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Saved search failed with ${response.status}`);
}

export async function importMetadata(
  format: "doi" | "bibtex" | "ris" | "csv",
  content: string,
): Promise<{ run_id: string; paper_ids: string[]; inserted_count: number; updated_count: number; error_count: number; errors: string[] }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/imports/metadata`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, content }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Metadata import failed with ${response.status}`);
  return await response.json() as {
    run_id: string; paper_ids: string[]; inserted_count: number; updated_count: number; error_count: number; errors: string[];
  };
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

export async function getCitationSnowball(id: string): Promise<CitationSnowball | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/papers/${id}/citations/snowball`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return await response.json() as CitationSnowball;
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

export async function uploadPrivatePdf(paperId: string, file: File): Promise<void> {
  const body = new FormData();
  body.set("file", file);
  body.set("rights_confirmed", "true");
  const response = await fetch(`${API_BASE_URL}/api/v1/papers/${paperId}/pdf`, {
    method: "POST",
    body,
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`PDF import failed with ${response.status}`);
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

export async function updateComparisonCell(
  comparisonId: string,
  cellId: string,
  valueText: string,
  evidenceChunkId?: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/comparison-sets/${comparisonId}/cells/${cellId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value_text: valueText, evidence_chunk_id: evidenceChunkId || null }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Comparison cell update failed with ${response.status}`);
}

export async function createGapAnalysis(
  topic: string,
  researchQuestionId?: string,
  retrievalLimit = 20,
): Promise<GapAnalysis> {
  const response = await fetch(`${API_BASE_URL}/api/v1/gap-analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, retrieval_limit: retrievalLimit, research_question_id: researchQuestionId ?? null }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Gap analysis API failed with ${response.status}`);
  }
  return (await response.json()) as GapAnalysis;
}

export async function listResearchQuestions(): Promise<ResearchQuestion[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/research-questions`, { cache: "no-store" });
    return response.ok ? await response.json() as ResearchQuestion[] : [];
  } catch {
    return [];
  }
}

export async function getResearchQuestion(id: string): Promise<ResearchQuestion | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/research-questions/${id}`, { cache: "no-store" });
    return response.ok ? await response.json() as ResearchQuestion : null;
  } catch {
    return null;
  }
}

export async function getResearchQuestionRecommendations(id: string): Promise<ResearchQuestionRecommendation[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/research-questions/${id}/recommendations`, {
      cache: "no-store",
    });
    return response.ok ? await response.json() as ResearchQuestionRecommendation[] : [];
  } catch {
    return [];
  }
}

export async function createResearchQuestion(payload: Record<string, unknown>): Promise<ResearchQuestion> {
  const response = await fetch(`${API_BASE_URL}/api/v1/research-questions`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), cache: "no-store",
  });
  if (!response.ok) throw new Error(`Research question create failed with ${response.status}`);
  return await response.json() as ResearchQuestion;
}

export async function updateResearchQuestion(id: string, payload: Record<string, unknown>): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/research-questions/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), cache: "no-store",
  });
  if (!response.ok) throw new Error(`Research question update failed with ${response.status}`);
}

export async function addResearchQuestionNote(id: string, note: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/research-questions/${id}/notes`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note_markdown: note }), cache: "no-store",
  });
  if (!response.ok) throw new Error(`Research question note failed with ${response.status}`);
}

export async function linkResearchQuestionEntity(
  id: string,
  kind: "papers" | "saved-searches" | "comparison-sets",
  entityId: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/research-questions/${id}/${kind}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ entity_id: entityId }), cache: "no-store",
  });
  if (!response.ok) throw new Error(`Research question link failed with ${response.status}`);
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
  scopeType: "corpus" | "papers" | "comparison_set" | "research_question" | "saved_search" = "corpus",
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

