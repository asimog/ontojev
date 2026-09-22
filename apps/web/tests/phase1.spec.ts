import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";

test("observes a complete durable synthetic research story", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.locator('[data-testid^="run-"], .panel.empty').first()).toBeVisible();
  const existingRunIds = await page.locator('[data-testid^="run-"]').evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-testid")!.replace("run-", "")),
  );
  const repositoryRoot = path.resolve(process.cwd(), "../..");
  const research = spawn("python", ["-m", "cancerjev", "run", "--fixture", "demo"], {
    cwd: repositoryRoot,
    env: { ...process.env, CANCERJEV_FIXTURE_STAGE_DELAY_MS: "500" },
    stdio: "pipe",
  });
  const output: string[] = [];
  research.stdout.on("data", (chunk) => output.push(chunk.toString()));
  research.stderr.on("data", (chunk) => output.push(chunk.toString()));

  try {
    const runId = await page.waitForFunction((known) => {
      const cards = [...document.querySelectorAll<HTMLElement>('[data-testid^="run-"]')];
      return cards.map((card) => card.dataset.testid!.replace("run-", "")).find((id) => !known.includes(id));
    }, existingRunIds).then((handle) => handle.jsonValue());
    expect(runId).toBeTruthy();
    const card = page.locator(`[data-testid="run-${runId}"]`);
    await card.getByRole("link", { name: "Open live run" }).click();
    await expect(page).toHaveURL(new RegExp(`/runs/${runId}$`));

    const observed = new Set<string>();
    const deadline = Date.now() + 30_000;
    let firstEventCount = 0;
    while (Date.now() < deadline && observed.size < 2) {
      const active = page.locator(".pipeline .active");
      if (await active.count()) observed.add((await active.innerText()).replace(" · live", ""));
      const count = await page.locator('[data-testid="event-feed"] details').count();
      if (!firstEventCount && count > 0) firstEventCount = count;
      await page.waitForTimeout(300);
    }
    expect(observed.size, `observed stages: ${[...observed].join(", ")}`).toBeGreaterThanOrEqual(2);
    await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    expect(await page.locator('[data-testid="event-feed"] details').count()).toBeGreaterThan(firstEventCount);
    await expect(page.locator('[data-testid="judgment-vector"]').first()).toBeVisible();
    await expect(page.getByText("GENERATED FIXTURE HYPOTHESES", { exact: true })).toBeVisible();
    await expect(page.getByText("REGISTERED FOLLOW-UP", { exact: true })).toBeVisible();

    await page.getByRole("link", { name: "Open dossier" }).click();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();
    await expect(page.getByText(/NO REAL GDC DATA WAS ANALYZED/).first()).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();

    await page.goto(`/runs/${runId}`);
    await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible();
    await expect(page.locator('[data-testid="event-feed"] details')).toHaveCount(71);
  } finally {
    if (research.exitCode === null) research.kill();
  }
  expect(output.join("")).toContain("[DONE]");
});
