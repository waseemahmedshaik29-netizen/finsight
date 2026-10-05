import { test, expect } from "@playwright/test";
test("portfolio research, valuation, stress, analyst and snapshot workflow", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const p = await request.post("http://localhost:8000/portfolios", {
    data: { name: "Browser regression", cash: 10000 },
  });
  const id = (await p.json()).id;
  await request.post(`http://localhost:8000/portfolios/${id}/positions`, {
    data: { ticker: "MSFT", quantity: 10, cost_basis: 320 },
  });
  try {
    await page.goto("/");
    await expect(page.getByText("Your portfolio, in focus.")).toBeVisible();
    await page
      .getByLabel("Portfolio", { exact: true })
      .selectOption(String(id));
    await expect(
      page.getByText("Growth of $100 · constant current holdings"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Risk", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Return correlations" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Research", exact: true }).click();
    await expect(
      page.getByText("FREE CASH FLOW", { exact: true }).first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.locator(".citation").first()).toContainText(
      "ILLUSTRATIVE",
    );
    await page.getByRole("button", { name: "Calculate valuation" }).click();
    await expect(
      page.getByText("IMPLIED SHARE PRICE", { exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Scenarios", exact: true }).click();
    await page.getByRole("button", { name: "Run stress test" }).click();
    await expect(page.getByText("ESTIMATED SCENARIO IMPACT")).toBeVisible();
    await page.getByRole("button", { name: "AI Analyst", exact: true }).click();
    await page.getByRole("button", { name: "Ask analyst" }).click();
    await expect(page.locator(".answer")).toContainText(
      "Historical one-day 95% VaR",
    );
    await expect(page.locator(".tool")).toContainText("portfolio analytics");
    await page.getByRole("button", { name: /^What Changed\?/ }).click();
    await page.getByRole("button", { name: "Capture snapshot" }).click();
    await expect(page.getByRole("status")).toContainText("Snapshot captured");
    await page
      .getByRole("button", { name: "Add position", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Ticker", { exact: true }).fill("NVDA");
    await dialog.getByLabel("Shares", { exact: true }).fill("20");
    await dialog.getByRole("button", { name: "Save position" }).click();
    await expect(dialog).not.toBeVisible();
    await page.getByRole("button", { name: "Capture snapshot" }).click();
    await expect(page.getByRole("status")).toContainText("Snapshot captured");
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Metric changes" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Allocation drift" }),
    ).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Export report", exact: true })
      .click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("finsight-committee-report.md");
    expect(errors).toEqual([]);
  } finally {
    await request.delete(`http://localhost:8000/portfolios/${id}`);
  }
});
test("responsive layout and validation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByText("Your portfolio, in focus.")).toBeVisible();
  await expect(page.locator(".metric").first()).toBeVisible();
  const width = await page.evaluate(() => ({
    content: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(width.content).toBeLessThanOrEqual(width.viewport);
  await page.getByTitle("Create portfolio").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
});
