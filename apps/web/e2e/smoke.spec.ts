import { expect, test } from "@playwright/test";

test("research workbench shell renders", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "What has the literature actually explained about AI and management of technology?" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Library", exact: true })).toBeVisible();
});

test("desktop sidebar expands on hover and can be pinned without overflowing", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");

  const sidebar = page.locator(".sidebar");
  const main = page.getByRole("main");
  const navigation = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(sidebar).toHaveCSS("width", "72px");
  await expect(main).toHaveCSS("margin-left", "0px");
  expect((await main.boundingBox())?.x).toBe(72);
  expect(await sidebar.evaluate((element) => element.scrollWidth)).toBe(72);
  await expect(page.locator(".brandMark")).toHaveCount(0);

  await sidebar.hover();
  await expect(sidebar).toHaveCSS("width", "284px");
  expect((await main.boundingBox())?.x).toBe(72);
  await expect(page.locator(".navHeaderRow")).toHaveCSS("flex-direction", "column");
  const sidebarBox = await sidebar.boundingBox();
  const navLinkBox = await navigation.getByRole("link", { name: "Library" }).boundingBox();
  expect(navLinkBox?.width ?? 999).toBeLessThan(sidebarBox?.width ?? 0);

  await page.getByRole("button", { name: "Pin navigation sidebar open" }).click();
  await expect(sidebar).toHaveClass(/sidebarPinnedOpen/);
  await main.hover();
  await expect(sidebar).toHaveCSS("width", "284px");
  expect((await main.boundingBox())?.x).toBe(284);

  await page.getByRole("button", { name: "Collapse navigation sidebar" }).click();
  await main.hover();
  await expect(sidebar).toHaveCSS("width", "72px");
  expect((await main.boundingBox())?.x).toBe(72);
});

test("mobile navigation does not push the research content below a full menu", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const title = page.locator(".researchThreadLead h2");
  await expect(title).toBeVisible();
  const box = await title.boundingBox();
  expect(box?.y ?? 999).toBeLessThan(280);

  await expect(page.getByRole("navigation", { name: "Quick navigation" })).toBeVisible();
  const primaryNavigation = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(primaryNavigation).toBeHidden();

  await page.getByRole("button", { name: "Open navigation menu" }).click();
  await expect(primaryNavigation).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: /Gap Canvas/ })).toBeVisible();
  await expect(primaryNavigation.getByText("Display language · 표시 언어")).toBeVisible();
  await primaryNavigation.getByRole("button", { name: "한국어" }).click();
  await expect(primaryNavigation.getByRole("link", { name: "연구 공백 캔버스" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(title).toHaveText("AI와 기술경영에 관해 기존 문헌은 실제로 무엇을 설명했을까요?");
  await primaryNavigation.getByRole("button", { name: "EN" }).click();
  await expect(title).toHaveText("What has the literature actually explained about AI and management of technology?");

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

  await page.getByLabel("Selected papers").getByRole("link", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Choose papers by title, not by database ID." })).toBeVisible();
  await expect(page.getByText("2/6 selected")).toBeVisible();

  await page.getByRole("link", { name: "Ask selected papers with evidence →" }).click();
  await expect(page.getByRole("heading", { name: "Ask a named research scope, not a database identifier." })).toBeVisible();
  await expect(page.getByText("2 selected papers")).toBeVisible();
});
