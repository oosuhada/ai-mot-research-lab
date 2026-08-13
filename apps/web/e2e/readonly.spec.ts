import { expect, test } from "@playwright/test";


const READ_ONLY_API = "http://127.0.0.1:18200";

test("read-only API independently rejects shared mutations", async ({ request }) => {
  const response = await request.post(`${READ_ONLY_API}/api/v1/research-questions`, {
    data: {
      title: "must not persist",
      question_text: "must not persist",
      evidence_status: "insufficient_evidence",
    },
  });

  expect(response.status()).toBe(403);
  expect((await response.json()).detail).toBe(
    "This deployment is a public read-only research demo. Mutations are disabled.",
  );
});

test("read-only web hides mutation controls while retaining research navigation", async ({ page, request }) => {
  await page.goto("/questions");
  await expect(page.locator(".questionReadOnlyPanel").getByText("Public Demo · Read-only")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create research workspace →" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Research question", exact: true })).toHaveCount(0);

  await page.goto("/imports");
  await expect(page.getByText("Public Demo · Import disabled")).toBeVisible();
  await expect(page.getByRole("button", { name: "Import metadata" })).toHaveCount(0);

  const browse = await request.get(`${READ_ONLY_API}/api/v1/papers?limit=1`);
  expect(browse.ok()).toBeTruthy();
  const payload = await browse.json() as { items: Array<{ id: string }> };
  const paperId = payload.items[0]?.id;
  expect(paperId).toBeTruthy();

  await page.goto(`/library/${paperId}`);
  const readingMargin = page.getByRole("complementary").filter({ hasText: "Margin" });
  await expect(readingMargin.getByText("Public Demo · Read-only")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save reading state" })).toHaveCount(0);
  await expect(page.getByPlaceholder("Add tag")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save note" })).toHaveCount(0);
  await expect(page.getByText("Uploads disabled in public demo")).toBeVisible();
});
