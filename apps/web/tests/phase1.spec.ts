import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";

const API_BASE = process.env.NEXT_PUBLIC_CANCERJEV_API_URL ?? "http://127.0.0.1:8000";
const FIXTURE_STAGE_DELAY_MS = "2500";

function runProcess(command: string, args: string[], cwd: string, env: Record<string, string>) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, stdio: "pipe" });
  const output: string[] = [];
  child.stdout.on("data", (chunk) => output.push(chunk.toString()));
  child.stderr.on("data", (chunk) => output.push(chunk.toString()));
  return { child, output };
}

async function waitForNewRunId(request: APIRequestContext, known: string[]): Promise<string> {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    const body = (await request.get(`${API_BASE}/api/runs?limit=50`).then((response) => response.json())) as { items: Array<{ run_id: string }> };
    const found = body.items.map((item) => item.run_id).find((id) => !known.includes(id));
    if (found) return found;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("new run did not appear in the API");
}

async function knownRunIds(request: APIRequestContext): Promise<string[]> {
  const body = (await request.get(`${API_BASE}/api/runs?limit=50`).then((response) => response.json())) as { items: Array<{ run_id: string }> };
  return body.items.map((item) => item.run_id);
}

async function firstEventId(request: APIRequestContext, runId: string): Promise<string> {
  const body = (await request.get(`${API_BASE}/api/runs/${runId}/events?after_sequence=0&limit=1`).then((response) => response.json())) as { items: Array<{ event_id: string }> };
  return body.items[0].event_id;
}

async function candidateOptionValues(page: Page): Promise<string[]> {
  return page.locator("section.filter-row select").first().locator("option").evaluateAll((nodes) => nodes.map((node) => (node as HTMLOptionElement).value));
}

test("observes a complete durable synthetic research story", async ({ page, request }) => {
  test.setTimeout(180_000);
  await page.goto("/runs");
  await expect(page.locator('[data-testid^="run-"], .panel.empty').first()).toBeVisible();
  const existingRunIds = await knownRunIds(request);
  const repositoryRoot = path.resolve(process.cwd(), "../..");
  const research = runProcess("python", ["-m", "cancerjev", "run", "--fixture", "demo"], repositoryRoot, { CANCERJEV_FIXTURE_STAGE_DELAY_MS: FIXTURE_STAGE_DELAY_MS });

  try {
    // Identify the run through the API, then prove the autonomous run appears in the UI feed.
    const runId = await waitForNewRunId(request, existingRunIds);
    const card = page.locator(`[data-testid="run-${runId}"]`);
    await expect(card).toBeVisible({ timeout: 25_000 });
    await expect(card.getByText(/elapsed/)).toBeVisible();

    // Open the detail page while the run is still active and observe live progress.
    await page.goto(`/runs/${runId}`);
    await expect(page.locator('[data-testid="event-feed"] details').first()).toBeVisible({ timeout: 15_000 });
    const observed = new Set<string>();
    const deadline = Date.now() + 60_000;
    let firstEventCount = 0;
    while (Date.now() < deadline && observed.size < 2) {
      const active = page.locator(".pipeline .active");
      if (await active.count()) observed.add((await active.innerText()).replace(" · live", ""));
      const count = await page.locator('[data-testid="event-feed"] details').count();
      if (!firstEventCount && count > 0) firstEventCount = count;
      await page.waitForTimeout(250);
    }
    expect(observed.size, `observed stages: ${[...observed].join(", ")}`).toBeGreaterThanOrEqual(2);
    expect(firstEventCount).toBeGreaterThan(0);

    // Auto-follow: a reader who scrolls up is not forced back down; new events are announced.
    const feed = page.locator('[data-testid="event-feed"]');
    await feed.evaluate((node) => { node.scrollTop = 0; });
    const scrolledTop = await feed.evaluate((node) => node.scrollTop);
    await expect(page.getByRole("button", { name: /new events/ })).toBeVisible({ timeout: 30_000 });
    expect(await feed.evaluate((node) => node.scrollTop)).toBe(scrolledTop);
    await page.getByRole("button", { name: /new events/ }).click();

    // Refresh while active: history is reconstructed from the API and polling resumes.
    const beforeReload = await page.locator('[data-testid="event-feed"] details').count();
    await page.reload();
    await expect(page.locator('[data-testid="event-feed"] details').first()).toBeVisible({ timeout: 15_000 });
    await expect.poll(() => page.locator('[data-testid="event-feed"] details').count(), { timeout: 30_000 }).toBeGreaterThanOrEqual(beforeReload);

    await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('[data-testid="event-feed"] details')).toHaveCount(71);
    await expect(page.locator('[data-testid="judgment-vector"]').first()).toContainText("/ 4");
    await expect(page.getByText("GENERATED FIXTURE HYPOTHESES", { exact: true })).toBeVisible();
    await expect(page.getByText("REGISTERED FOLLOW-UP", { exact: true })).toBeVisible();
    await expect(page.getByTestId("budget-summary")).toContainText("GDC requests");
    await expect(page.getByTestId("budget-summary")).toContainText("unknown");

    const firstEvent = page.locator('[data-testid="event-feed"] details').first();
    await expect(firstEvent.locator("summary")).toContainText("RUN_CREATED");
    await firstEvent.locator("summary").click();
    await expect(firstEvent.locator(".event-data")).toBeVisible();
    await firstEvent.locator("summary").click();

    // Dossier provenance must show a real artifact id and the served 64-hex digest.
    await page.getByRole("link", { name: "Open dossier" }).click();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();
    await expect(page.getByText(/NO REAL GDC DATA WAS ANALYZED/).first()).toBeVisible();
    const provenance = page.getByTestId("dossier-provenance");
    await expect(provenance).not.toContainText("unavailable");
    await expect(provenance).not.toContainText("artifact —");
    const provenanceText = await provenance.innerText();
    const digest = provenanceText.match(/sha256 ([0-9a-f]{64})/)?.[1];
    expect(digest, `provenance text: ${provenanceText}`).toBeTruthy();
    const dossierId = page.url().split("/dossiers/")[1];
    const servedDossier = await request.get(`${API_BASE}/api/dossiers/${dossierId}`);
    expect(servedDossier.headers()["x-artifact-sha256"]).toBe(digest);
    expect(servedDossier.headers()["x-artifact-id"]).toMatch(/^[0-9a-f-]{36}$/);
    await expect(page.getByRole("link", { name: "Download authoritative JSON" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download derived Markdown" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();

    await page.goto(`/runs/${runId}`);
    await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible();
    await expect(page.locator('[data-testid="event-feed"] details')).toHaveCount(71);

    const served = (await request.get(`${API_BASE}/api/runs/${runId}/events?after_sequence=0&limit=500`).then((response) => response.json())) as { run_last_sequence: number; items: Array<{ event_id: string }> };
    expect(served.run_last_sequence).toBe(71);
    const show = runProcess("python", ["-m", "cancerjev", "show", runId, "--events"], repositoryRoot, {});
    await new Promise((resolve) => show.child.on("close", resolve));
    const cliIds = [...show.output.join("").matchAll(/"event_id":\s*"([0-9a-f-]{36})"/g)].map((match) => match[1]);
    expect(cliIds).toEqual(served.items.map((event) => event.event_id));
  } finally {
    if (research.child.exitCode === null) research.child.kill();
  }
  expect(research.output.join("")).toContain("[DONE]");
});

test("run detail resets run-scoped state on a client-side run change", async ({ page, request }) => {
  test.setTimeout(150_000);
  const repositoryRoot = path.resolve(process.cwd(), "../..");
  const created: string[] = [];
  for (let index = 0; index < 2; index += 1) {
    const known = await knownRunIds(request);
    const research = runProcess("python", ["-m", "cancerjev", "run", "--fixture", "demo"], repositoryRoot, { CANCERJEV_FIXTURE_STAGE_DELAY_MS: "0" });
    const runId = await waitForNewRunId(request, known);
    await new Promise((resolve) => research.child.on("close", resolve));
    expect(research.output.join("")).toContain("[DONE]");
    created.push(runId);
  }
  const [older, newer] = created;
  const olderFirstEvent = await firstEventId(request, older);
  const newerFirstEvent = await firstEventId(request, newer);
  expect(olderFirstEvent).not.toBe(newerFirstEvent);

  const pushClientSide = async (url: string) => {
    await page.evaluate((target) => {
      const router = (window as unknown as { next?: { router?: { push?: (href: string) => void } } }).next?.router;
      if (!router?.push) throw new Error("Next.js client router is unavailable");
      router.push(target);
    }, url);
  };

  await page.goto(`/runs/${newer}`);
  await expect(page.locator('[data-testid="event-feed"] details')).toHaveCount(71, { timeout: 30_000 });
  const newerCandidates = await candidateOptionValues(page);
  await page.evaluate(() => { (window as unknown as { __cjMarker?: string }).__cjMarker = "kept"; });

  // In-app client-side transition to a different run without a document reload.
  await pushClientSide(`/runs/${older}`);
  await expect(page).toHaveURL(new RegExp(`/runs/${older}$`));
  expect(await page.evaluate(() => (window as unknown as { __cjMarker?: string }).__cjMarker)).toBe("kept");
  await expect(page.locator('[data-testid="event-feed"] details')).toHaveCount(71);
  await expect.poll(() => page.locator('[data-testid="event-feed"] details').first().getAttribute("data-event-id")).toBe(olderFirstEvent);
  await expect.poll(() => candidateOptionValues(page), { timeout: 10_000 }).not.toEqual(newerCandidates);

  // And back again; the feed must never retain the other run's events.
  await pushClientSide(`/runs/${newer}`);
  await expect(page).toHaveURL(new RegExp(`/runs/${newer}$`));
  expect(await page.evaluate(() => (window as unknown as { __cjMarker?: string }).__cjMarker)).toBe("kept");
  await expect.poll(() => page.locator('[data-testid="event-feed"] details').first().getAttribute("data-event-id")).toBe(newerFirstEvent);
  await expect.poll(() => candidateOptionValues(page), { timeout: 10_000 }).toEqual(newerCandidates);
});
