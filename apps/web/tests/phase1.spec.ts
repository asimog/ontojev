import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";

function runProcess(command: string, args: string[], cwd: string, env: Record<string, string>) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, stdio: "pipe" });
  const output: string[] = [];
  child.stdout.on("data", (chunk) => output.push(chunk.toString()));
  child.stderr.on("data", (chunk) => output.push(chunk.toString()));
  return { child, output };
}

test("observes a complete durable synthetic research story", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.locator('[data-testid^="run-"], .panel.empty').first()).toBeVisible();
  const existingRunIds = await page.locator('[data-testid^="run-"]').evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-testid")!.replace("run-", "")),
  );
  const repositoryRoot = path.resolve(process.cwd(), "../..");
  const research = runProcess("python", ["-m", "cancerjev", "run", "--fixture", "demo"], repositoryRoot, { CANCERJEV_FIXTURE_STAGE_DELAY_MS: "500" });

  try {
    const runId = await page.waitForFunction((known) => {
      const cards = [...document.querySelectorAll<HTMLElement>('[data-testid^="run-"]')];
      return cards.map((card) => card.dataset.testid!.replace("run-", "")).find((id) => !known.includes(id));
    }, existingRunIds).then((handle) => handle.jsonValue() as Promise<string | undefined>);
    expect(runId).toBeTruthy();
    if (!runId) throw new Error("new run card did not appear");
    const card = page.locator(`[data-testid="run-${runId}"]`);
    await expect(card.getByText(/elapsed/)).toBeVisible();
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
    await expect(page.getByTestId("budget-summary")).toContainText("GDC requests");
    await expect(page.getByTestId("budget-summary")).toContainText("unknown");

    const firstEvent = page.locator('[data-testid="event-feed"] details').first();
    await expect(firstEvent.locator("summary")).toContainText("RUN_CREATED");
    await firstEvent.locator("summary").click();
    await expect(firstEvent.locator(".event-data")).toBeVisible();
    await firstEvent.locator("summary").click();

    await page.getByRole("link", { name: "Open dossier" }).click();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();
    await expect(page.getByText(/NO REAL GDC DATA WAS ANALYZED/).first()).toBeVisible();
    await expect(page.getByTestId("dossier-provenance")).toContainText("sha256");
    await expect(page.getByRole("link", { name: "Download authoritative JSON" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download derived Markdown" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();

    await page.goto(`/runs/${runId}`);
    await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible();
    await expect(page.locator('[data-testid="event-feed"] details')).toHaveCount(71);

    const apiBase = process.env.NEXT_PUBLIC_CANCERJEV_API_URL ?? "http://127.0.0.1:8000";
    const served = await fetch(`${apiBase}/api/runs/${runId}/events?after_sequence=0&limit=500`).then((response) => response.json());
    expect(served.run_last_sequence).toBe(71);
    const show = runProcess("python", ["-m", "cancerjev", "show", runId, "--events"], repositoryRoot, {});
    await new Promise((resolve) => show.child.on("close", resolve));
    const cliIds = [...show.output.join("").matchAll(/"event_id":\s*"([0-9a-f-]{36})"/g)].map((match) => match[1]);
    expect(cliIds).toEqual(served.items.map((event: { event_id: string }) => event.event_id));
  } finally {
    if (research.child.exitCode === null) research.child.kill();
  }
  expect(research.output.join("")).toContain("[DONE]");
});
