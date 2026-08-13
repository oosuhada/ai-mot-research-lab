import { API_BASE_URL } from "@/lib/api";

const allowedFormats = new Set(["markdown", "csv"]);

export async function GET(
  request: Request,
  context: { params: Promise<{ comparisonId: string }> },
) {
  const { comparisonId } = await context.params;
  const requestUrl = new URL(request.url);
  const format = requestUrl.searchParams.get("format") ?? "markdown";

  if (!allowedFormats.has(format)) {
    return Response.json({ detail: "Unsupported export format." }, { status: 400 });
  }

  const upstream = await fetch(
    `${API_BASE_URL}/api/v1/comparison-sets/${encodeURIComponent(comparisonId)}/export?format=${format}`,
    { cache: "no-store" },
  );

  if (!upstream.ok) {
    return Response.json(
      { detail: "The comparison export could not be generated." },
      { status: upstream.status },
    );
  }

  const headers = new Headers();
  for (const name of ["content-type", "content-disposition"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("cache-control", "no-store");

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
