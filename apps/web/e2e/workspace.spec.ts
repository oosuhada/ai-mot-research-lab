import { expect, test, type APIRequestContext, type Page } from "@playwright/test";


const WRITABLE_API = "http://127.0.0.1:18100";

type BrowsePayload = {
  total: number;
  items: Array<{ id: string; title: string }>;
};

async function seededPaperIds(request: APIRequestContext, count = 2): Promise<string[]> {
  const response = await request.get(`${WRITABLE_API}/api/v1/papers?limit=${count}`);
  expect(response.ok()).toBeTruthy();
  const payload = await response.json() as BrowsePayload;
  expect(payload.items).toHaveLength(count);
  return payload.items.map((paper) => paper.id);
}

async function resultPaperIds(page: Page): Promise<string[]> {
  const hrefs = await page.locator(".paperResult h3 a").evaluateAll((links) =>
    links.map((link) => link.getAttribute("href") ?? ""),
  );
  return hrefs.map((href) => href.split("/").pop() ?? "").filter(Boolean);
}

test("Browse All Papers traverses the full corpus without duplicates or omissions", async ({ page }) => {
  await page.goto("/library?view=browse");

  await expect(page.getByRole("link", { name: /Browse All Papers/ })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("Showing papers 1–10 of 125")).toBeVisible();
  await expect(page.getByText(/candidate pool capped at/)).toHaveCount(0);

  const visited = new Set<string>();
  let expectedStart = 1;
  let previousPageIds: string[] | null = null;

  while (true) {
    const expectedEnd = Math.min(expectedStart + 9, 125);
    await expect(page.getByText(`Showing papers ${expectedStart}–${expectedEnd} of 125`)).toBeVisible();
    const ids = await resultPaperIds(page);
    expect(ids.length).toBeGreaterThan(0);
    for (const id of ids) {
      expect(visited.has(id)).toBeFalsy();
      visited.add(id);
    }
    previousPageIds = ids;

    const end = expectedStart + ids.length - 1;
    const next = page.getByRole("link", { name: "Next →" });
    if (await next.count() === 0) break;
    await next.click();
    expectedStart = end + 1;
  }

  expect(visited.size).toBe(125);
  expect(expectedStart).toBe(121);
  expect(previousPageIds).not.toBeNull();
  await expect(page.getByText("Showing papers 121–125 of 125")).toBeVisible();

  await page.getByRole("link", { name: "← Previous" }).click();
  await expect(page.getByText("Showing papers 111–120 of 125")).toBeVisible();
  const priorIds = await resultPaperIds(page);
  expect(priorIds.every((id) => visited.has(id))).toBeTruthy();
});

test("Search Results retains the ranked top-100 pool and filter changes reset cursors", async ({ page }) => {
  await page.goto("/library?view=search&q=AI%20capability&mode=hybrid");

  await expect(page.getByRole("link", { name: /Search Results/ })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText(/Showing 1–10 of 100\+ ranked candidates/)).toBeVisible();
  await expect(page.getByText(/candidate pool capped at 100/)).toBeVisible();

  await page.goto("/library?view=browse");
  await page.getByRole("link", { name: "Next →" }).click();
  await expect(page).toHaveURL(/cursor=/);
  await expect(page.getByText("Showing papers 11–20 of 125")).toBeVisible();

  await page.locator("details.advancedFilters summary").click();
  await page.getByLabel("Year from").fill("2023");
  await page.getByRole("button", { name: "Apply browse filters" }).click();
  await expect(page).toHaveURL(/view=browse/);
  await expect(page).not.toHaveURL(/cursor=/);
  await expect(page.getByText("Showing papers 1–10 of 50")).toBeVisible();

  await page.getByRole("link", { name: /Search Results/ }).click();
  await expect(page).not.toHaveURL(/cursor=/);
});

test("mobile mode switching and cursor pagination remain usable at 390 by 844", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/library?view=browse");

  await expect(page.getByRole("navigation", { name: "Library mode" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Search Results/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Browse All Papers/ })).toBeVisible();
  await page.getByRole("link", { name: "Next →" }).click();
  await expect(page.getByText("Showing papers 11–20 of 125")).toBeVisible();
  await page.getByRole("link", { name: /Search Results/ }).click();
  await expect(page.getByText("Start with a research idea.")).toBeVisible();
});

test("writable workspace completes core CRUD flows with inline success and failure feedback", async ({ page, request }) => {
  test.setTimeout(90_000);
  await page.goto("/questions");
  await page.getByLabel("Working title").fill("Writable E2E research question");
  await page.getByRole("textbox", { name: "Research question", exact: true }).fill("How does AI capability influence innovation performance in the E2E fixture corpus?");
  await page.getByRole("button", { name: "Create research workspace →" }).click();
  await expect(page).toHaveURL(/\/questions\/[0-9a-f-]+\?feedback=created/);
  await expect(page.getByText("Research question created.")).toBeVisible();

  await page.goto("/imports");
  await page.getByLabel("Format").selectOption("csv");
  await page.locator('textarea[name="content"]').fill([
    "doi,title,abstract,year,authors",
    "10.9999/e2e.imported,Writable E2E imported paper,AI capability import fixture with provenance,2025,E2E Import Author",
  ].join("\n"));
  await page.getByRole("button", { name: "Import metadata" }).click();
  await expect(page).toHaveURL(/\/library\/[0-9a-f-]+\?imported=1/);
  await expect(page.getByText(/Metadata imported successfully/)).toBeVisible();

  const readingForm = page.locator("form").filter({ hasText: "Save reading state" });
  await readingForm.locator("select").selectOption("reading");
  await readingForm.getByLabel("Priority (0–100)").fill("77");
  await readingForm.getByRole("button", { name: "Save reading state" }).click();
  await expect(page.getByText("Reading state saved.")).toBeVisible();

  const tag = "e2e-workspace-tag";
  await page.getByPlaceholder("Add tag").fill(tag);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Tag added.")).toBeVisible();
  await page.getByRole("button", { name: `${tag} ×` }).click();
  await expect(page.getByText("Tag removed.")).toBeVisible();

  const note = "Writable E2E research note";
  await page.getByPlaceholder("Your interpretation, question, or reading note").fill(note);
  await page.getByPlaceholder("Optional source locator, e.g. abstract or p. 7").fill("abstract");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect(page.getByText("Research note saved.")).toBeVisible();
  await expect(page.getByText(note)).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("Research note removed.")).toBeVisible();
  await expect(page.getByText(note)).toHaveCount(0);

  const [firstPaperId, secondPaperId] = await seededPaperIds(request, 2);
  await page.goto(`/compare?papers=${firstPaperId},${secondPaperId}`);
  await page.getByPlaceholder("e.g. AI capability mechanisms").fill("Writable E2E comparison");
  await page.getByRole("button", { name: "Create comparison" }).click();
  await expect(page).toHaveURL(/\/compare\?id=[0-9a-f-]+&feedback=created/);
  await expect(page.getByText("Comparison set created.")).toBeVisible();

  const firstEditor = page.locator("details.comparisonEdit").first();
  await firstEditor.locator("summary").click();
  await firstEditor.locator('textarea[name="value_text"]').fill("User-reviewed E2E comparison note");
  await firstEditor.getByRole("button", { name: "Save cell" }).click();
  await expect(page.getByText("Comparison note saved.")).toBeVisible();

  const missingOne = "00000000-0000-4000-8000-000000000001";
  const missingTwo = "00000000-0000-4000-8000-000000000002";
  await page.goto(`/compare?papers=${missingOne},${missingTwo}`);
  await page.getByRole("button", { name: "Create comparison" }).click();
  await expect(page).toHaveURL(/feedback=error/);
  await expect(page.getByText("The comparison change could not be saved. Your current selection is still available.")).toBeVisible();
  await expect(page.getByText(/Internal Server Error|Traceback|HTTPException/)).toHaveCount(0);

  await page.goto("/gap-canvas");
  const gapTopic = page.locator('input[name="topic"]');
  await gapTopic.fill("AI capability and innovation performance");
  await page.getByRole("button", { name: "Build evidence canvas →" }).click();
  await expect(page).toHaveURL(/\/gap-canvas\?id=[0-9a-f-]+&feedback=created/);
  await expect(page.getByText(/Gap Canvas created/)).toBeVisible();

  await page.locator('textarea[name="agreements"]').fill("Writable E2E synthesis note");
  await page.getByRole("button", { name: "Save synthesis notes" }).click();
  await expect(page.getByText("Research synthesis notes saved.")).toBeVisible();

  await page.goto("/gap-canvas");
  await gapTopic.fill("AI");
  await gapTopic.evaluate((element) => element.closest("form")?.setAttribute("novalidate", ""));
  await page.getByRole("button", { name: "Build evidence canvas →" }).click();
  await expect(page).toHaveURL(/feedback=invalid-topic/);
  await expect(page.getByText("Enter a research topic with at least three characters.")).toBeVisible();
});
