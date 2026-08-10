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

export const API_BASE_URL =
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

