import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";

const API_BASE = process.env.NEXT_PUBLIC_CANCERJEV_API_URL ?? "http://127.0.0.1:8000";
const REPOSITORY_ROOT = path.resolve(process.cwd(), "..", "..");

function runDemo() {
  return spawn("python", ["-m", "cancerjev", "run", "--fixture", "demo"], {
    cwd: REPOSITORY_ROOT,
    env: { ...process.env, CANCERJEV_FIXTURE_STAGE_DELAY_MS: "0" },
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
