import { expect, test } from "@playwright/test";

test("research workbench shell renders", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Turn a vague research interest into an evidence-backed question" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Library/ })).toBeVisible();
});

test("mobile navigation does not push the research content below a full menu", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const title = page.getByRole("heading", {
    name: "Turn a vague research interest into an evidence-backed question",
  });
  await expect(title).toBeVisible();
  const box = await title.boundingBox();
  expect(box?.y ?? 999).toBeLessThan(280);

  await expect(page.getByRole("navigation", { name: "Quick navigation" })).toBeVisible();
  const primaryNavigation = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(primaryNavigation).toBeHidden();

  await page.getByRole("button", { name: "Open navigation menu" }).click();
  await expect(primaryNavigation).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: /Gap Canvas/ })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(primaryNavigation).toBeHidden();
  await expect(page.getByRole("button", { name: "Open navigation menu" })).toBeFocused();
});

test("library pagination and research question context persist across workflows", async ({ page, request }) => {
  const health = await request.get("http://127.0.0.1:8000/health").catch(() => null);
  test.skip(!health?.ok(), "Library pagination E2E requires the local API on port 8000.");

  await page.goto("/library?q=AI%20capability&mode=hybrid");
  const selectButtons = page.getByRole("button", { name: "+ Select" });
  await expect(selectButtons).toHaveCount(10);
  await expect(page.getByText(/Showing 1–10 of 100\+ ranked candidates/)).toBeVisible();

  const currentQuestion = page.getByRole("combobox", { name: "Current research question" });
  await expect(currentQuestion).toBeVisible();
  const options = currentQuestion.locator("option");
  const firstQuestionValue = await options.count() >= 2 ? await options.nth(1).getAttribute("value") : null;
  if (firstQuestionValue) await currentQuestion.selectOption(firstQuestionValue);

  await page.getByRole("link", { name: "Next →" }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByText(/Showing 11–20 of 100\+ ranked candidates/)).toBeVisible();
  await expect(page.getByRole("button", { name: "+ Select" })).toHaveCount(10);

  if (firstQuestionValue) {
    await page.goto("/compare");
    await expect(page.getByRole("combobox", { name: "Current research question" })).toHaveValue(firstQuestionValue);

    await page.goto("/chat");
    await expect(page.getByRole("combobox", { name: "Current research question" })).toHaveValue(firstQuestionValue);
  }
});

test("search selection flows into compare and evidence chat", async ({ page, request }) => {
  const health = await request.get("http://127.0.0.1:8000/health").catch(() => null);
  test.skip(!health?.ok(), "Full research-flow E2E requires the local API on port 8000.");

  await page.goto("/library?q=AI%20capability&mode=hybrid");
  const selectButtons = page.getByRole("button", { name: "+ Select" });
  await expect(selectButtons.first()).toBeVisible();

  await selectButtons.first().click();
  await page.getByRole("button", { name: "+ Select" }).first().click();
  await expect(page.getByText("2 papers selected")).toBeVisible();

  await page.getByRole("link", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Choose papers by title, not by database ID." })).toBeVisible();
  await expect(page.getByText("2/6 selected")).toBeVisible();

  await page.getByRole("link", { name: "Ask selected papers with evidence →" }).click();
  await expect(page.getByRole("heading", { name: "Ask a named research scope, not a database identifier." })).toBeVisible();
  await expect(page.getByText("2 selected papers")).toBeVisible();
});

