import { expect, test } from "@playwright/test";

test("research workbench shell renders", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Turn a vague research interest into an evidence-backed question" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Library/ })).toBeVisible();
});

