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

