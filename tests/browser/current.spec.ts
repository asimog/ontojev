import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";

const API_BASE = process.env.NEXT_PUBLIC_CANCERJEV_API_URL ?? "http://127.0.0.1:8000";
const REPOSITORY_ROOT = path.resolve(process.cwd(), "..", "..");

function runDemo(stageDelayMs = "0") {
  return spawn("python", ["-m", "cancerjev", "run", "--fixture", "demo"], {
    cwd: REPOSITORY_ROOT,
    env: { ...process.env, CANCERJEV_FIXTURE_STAGE_DELAY_MS: stageDelayMs },
    stdio: "pipe",
  });
}

async function knownRunIds(request: APIRequestContext): Promise<string[]> {
  const body = (await request
    .get(`${API_BASE}/api/runs?limit=50`)
    .then((response) => response.json())) as { items: Array<{ run_id: string }> };
  return body.items.map((item) => item.run_id);
}

async function waitForNewRunId(request: APIRequestContext, known: string[]): Promise<string> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const found = (await knownRunIds(request)).find((id) => !known.includes(id));
    if (found) return found;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("demo run did not appear in the API");
}

async function waitForRunCompleted(request: APIRequestContext, runId: string): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const run = (await request
      .get(`${API_BASE}/api/runs/${runId}`)
      .then((response) => response.json())) as { status: string };
    if (run.status === "COMPLETED") return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`run ${runId} did not complete`);
}

async function firstEventId(request: APIRequestContext, runId: string): Promise<string> {
  const body = (await request
    .get(`${API_BASE}/api/runs/${runId}/events?after_sequence=0&limit=1`)
    .then((response) => response.json())) as { items: Array<{ event_id: string }> };
  return body.items[0].event_id;
}

async function candidateOptionValues(page: Page): Promise<string[]> {
  return page
    .locator("section.filter-row select")
    .first()
    .locator("option")
    .evaluateAll((nodes) => nodes.map((node) => (node as HTMLOptionElement).value));
}

async function waitForEventType(
  request: APIRequestContext,
  runId: string,
  eventType: string,
): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const body = (await request
      .get(`${API_BASE}/api/runs/${runId}/events?after_sequence=0&limit=500`)
      .then((response) => response.json())) as { items: Array<{ type: string }> };
    if (body.items.some((event) => event.type === eventType)) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`event ${eventType} was not recorded`);
}

async function assertDurableCurrentStory(page: Page, request: APIRequestContext, runId: string) {
  await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible({
    timeout: 120_000,
  });
  // RunDetail reads child records once at mount; reload so the committed story (states,
  // evidence, dossier) is rebuilt from the completed run rather than the in-flight one.
  await page.reload();
  await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible({
    timeout: 120_000,
  });
  await expect(page.locator('[data-testid="event-feed"] details').first()).toBeVisible();
  // Fixture mode renders the synthetic deterministic-evidence section (the LIVE-only
  // DeterministicStatePanel is not part of this workflow).
  await expect(page.getByText("DETERMINISTIC / FIXTURE EVIDENCE")).toBeVisible();
  await expect(page.getByText(/synthetic statistical states/)).toBeVisible();
  await expect(page.getByText("GENEONE").first()).toBeVisible();

  const states = (await request
    .get(`${API_BASE}/api/runs/${runId}/states`)
    .then((response) => response.json())) as { items: Array<{ summary: { entity: { gene_symbol: string } } }> };
  expect(states.items.length).toBeGreaterThanOrEqual(1);

  await waitForEventType(request, runId, "DOSSIER_CREATED");
  await page.getByRole("link", { name: "Open dossier" }).click();
  await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();
  await expect(page.getByText(/NO REAL GDC DATA WAS ANALYZED/).first()).toBeVisible();

  const provenance = page.getByTestId("dossier-provenance");
  await expect(provenance).not.toContainText("unavailable");
  const digest = (await provenance.innerText()).match(/sha256 ([0-9a-f]{64})/)?.[1];
  expect(digest).toBeTruthy();
  const dossierId = page.url().split("/dossiers/")[1];
  const servedDossier = await request.get(`${API_BASE}/api/dossiers/${dossierId}`);
  expect(servedDossier.headers()["x-artifact-sha256"]).toBe(digest);
  expect(servedDossier.headers()["x-artifact-id"]).toMatch(/^[0-9a-f-]{36}$/);
  const dossier = (await servedDossier.json()) as { warning: string };
  expect(dossier.warning).toContain("SYNTHETIC DEMONSTRATION");

  const markdown = await request.get(`${API_BASE}/api/dossiers/${dossierId}?format=markdown`);
  expect(markdown.ok()).toBeTruthy();
  expect(await markdown.text()).toContain("SYNTHETIC DEMONSTRATION");
}

test("shared typed demo run is observed end to end in the browser", async ({ page, request }) => {
  test.setTimeout(300_000);
  await page.goto("/runs");
  const known = await knownRunIds(request);
  const research = runDemo();
  try {
    const runId = await waitForNewRunId(request, known);
    const card = page.locator(`[data-testid="run-${runId}"]`);
    await expect(card).toBeVisible({ timeout: 30_000 });

    await page.goto(`/runs/${runId}`);
    await assertDurableCurrentStory(page, request, runId);

    // Durable restart: reloading the dossier rebuilds the same committed story.
    await page.reload();
    await expect(page.getByRole("heading", { name: "SYNTHETIC DEMONSTRATION" })).toBeVisible();

    const served = (await request
      .get(`${API_BASE}/api/runs/${runId}/events?after_sequence=0&limit=500`)
      .then((response) => response.json())) as { run_last_sequence: number; items: Array<{ event_id: string }> };
    expect(served.run_last_sequence).toBe(served.items.length);
    const sequences = served.items.map((event) => event.event_id);
    expect(new Set(sequences).size).toBe(sequences.length);
  } finally {
    if (research.exitCode === null) research.kill();
  }
});

test("a scrolled-up reader keeps position, is told about new events and resumes on request", async ({ page, request }) => {
  test.setTimeout(300_000);
  await page.goto("/runs");
  const known = await knownRunIds(request);
  const research = runDemo("2500");
  try {
    const runId = await waitForNewRunId(request, known);
    await page.goto(`/runs/${runId}`);
    const feed = page.locator('[data-testid="event-feed"]');
    await expect(feed.locator("details").first()).toBeVisible({ timeout: 60_000 });
    await expect
      .poll(() => feed.locator("details").count(), { timeout: 120_000 })
      .toBeGreaterThanOrEqual(10);

    // Auto-follow: a reader who scrolls up is not forced back down; new events are announced.
    const scrolledTop = await feed.evaluate((node) => {
      node.scrollTop = 0;
      return node.scrollTop;
    });
    await expect(page.getByRole("button", { name: /new events/ })).toBeVisible({ timeout: 60_000 });
    expect(await feed.evaluate((node) => node.scrollTop)).toBe(scrolledTop);
    await page.getByRole("button", { name: /new events/ }).click();
    await expect(page.getByRole("button", { name: /new events/ })).toHaveCount(0);
    expect(await feed.evaluate((node) => node.scrollTop)).toBeGreaterThan(scrolledTop);

    // Refresh while active: the retained history is reconstructed and polling resumes.
    const beforeReload = await feed.locator("details").count();
    await page.reload();
    await expect(feed.locator("details").first()).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(() => feed.locator("details").count(), { timeout: 60_000 })
      .toBeGreaterThanOrEqual(beforeReload);
  } finally {
    if (research.exitCode === null) research.kill();
  }
});

test("run detail resets run-scoped state on a client-side run switch", async ({ page, request }) => {
  test.setTimeout(300_000);
  const created: string[] = [];
  for (let index = 0; index < 2; index += 1) {
    const known = await knownRunIds(request);
    const research = runDemo();
    try {
      const runId = await waitForNewRunId(request, known);
      created.push(runId);
      await waitForRunCompleted(request, runId);
    } finally {
      if (research.exitCode === null) research.kill();
    }
  }
  const [older, newer] = created;
  const olderFirstEvent = await firstEventId(request, older);
  const newerFirstEvent = await firstEventId(request, newer);
  expect(olderFirstEvent).not.toBe(newerFirstEvent);

  await page.goto("/runs");
  await page.locator(`[data-testid="run-${newer}"]`).getByRole("link", { name: /Open run/ }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${newer}$`));
  const feed = page.locator('[data-testid="event-feed"]');
  await expect
    .poll(() => feed.locator("details").first().getAttribute("data-event-id"), { timeout: 60_000 })
    .toBe(newerFirstEvent);
  const newerCandidates = await candidateOptionValues(page);
  await page.evaluate(() => {
    (window as unknown as { __cjMarker?: string }).__cjMarker = "kept";
  });

  // In-app client-side transition to the other run without a document reload.
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await expect(page).toHaveURL(/\/runs$/);
  await page.locator(`[data-testid="run-${older}"]`).getByRole("link", { name: /Open run/ }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${older}$`));
  expect(await page.evaluate(() => (window as unknown as { __cjMarker?: string }).__cjMarker)).toBe("kept");
  await expect
    .poll(() => feed.locator("details").first().getAttribute("data-event-id"), { timeout: 60_000 })
    .toBe(olderFirstEvent);
  await expect.poll(() => candidateOptionValues(page), { timeout: 30_000 }).not.toEqual(newerCandidates);

  // And back again; the feed must never retain the other run's events.
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await page.locator(`[data-testid="run-${newer}"]`).getByRole("link", { name: /Open run/ }).click();
  await expect
    .poll(() => feed.locator("details").first().getAttribute("data-event-id"), { timeout: 60_000 })
    .toBe(newerFirstEvent);
  await expect.poll(() => candidateOptionValues(page), { timeout: 30_000 }).toEqual(newerCandidates);
});
