import { expect, test } from "@playwright/test";

test("research landscape shell renders", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Build a research map before asking for an answer." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Paper Library" })).toBeVisible();
});

