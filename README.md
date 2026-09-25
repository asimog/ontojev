# OntoJev — autonomous computational-genomics target discovery

OntoJev is:

> An autonomous computational-genomics target-discovery system using deterministic genomic
> analysis to create structured evidence, Jev to judge potentially interesting patterns,
> bounded LLM-generated hypotheses where useful, Jev to critique those hypotheses, and
> Python to control all execution and evidence creation.

It retrieves public, open-access GDC data through one bounded anonymous transport, measures
it with deterministic scientific methods, and never sends raw genomic data to Jev. The
invariant pipeline is:

```text
raw genomics
  → strict parsing
  → deterministic computational genomics
  → typed genomic features
  → Jev
```

Never `raw genomics → Jev`. The division of control is always:

```text
Jev judges.
Python decides.
Python executes.
```

## Research hypothesis

> Can deterministic computational genomics combined with selective Jev semantic judgment
> identify cancer target candidates whose potential importance arises from unusual,
> discordant, multi-modal, under-ranked, or otherwise non-obvious genomic patterns that
> conventional deterministic discovery may overlook?

The question deliberately says **potential importance**, not "significance": OntoJev is
discovering and investigating computational target candidates, not establishing biological
or clinical validation.

## Product

OntoJev is a continuously operating autonomous computational-genomics target-discovery
system composed of bounded, reproducible research campaigns. It transforms large cancer
genomic cohorts into deterministic mutation, expression and CNV features, uses deterministic
policies to identify candidates and cases where semantic judgment is useful, and applies Jev
selectively to surface non-obvious, discordant, multi-modal or under-ranked patterns. Wide
Jev helps identify targets worth deeper investigation; Deep Jev evaluates what remains
unexplained and whether additional computation or hypothesis generation has information
value. Python controls candidate selection, registered scientific actions, evidence
revision, stopping and campaign progression. Bounded LLM-generated hypotheses may be
proposed for unresolved genomic patterns, but Jev critiques them and only registered
deterministic analyses can create new evidence. Each candidate ends in a reproducible final
result and dossier, including a deterministic Jev-vs-conventional baseline comparison,
before the system proceeds to the next candidate and ultimately the next bounded campaign.

## Primary execution model

The primary product is a **system-owned autonomous research program**. It exists
independently of any researcher UI. Researchers are an optional, isolated future route.

```text
SYSTEM AUTONOMOUS PROGRAM
        ↓
bounded campaign
        ↓
multi-modal target discovery
        ↓
target investigation
        ↓
Stage 8
        ↓
campaign complete
        ↓
next bounded campaign
```

This is not one infinite run: campaigns are bounded, independently reproducible, and each
ends in committed results before the next begins. An optional Researcher Lab may run
isolated researcher-defined investigations using the same scientific engine, but
researcher-run state, evidence, candidates, hypotheses and results are isolated from the
system-owned autonomous program at runtime.

**Researcher rule (testable):** researcher activity cannot influence the system-owned
autonomous program at runtime. Any influence on future autonomous behavior must occur
through an explicit versioned code/scientific change outside runtime. This does not claim
humans can never influence the project — it bounds *how* influence may occur.

## Runtime loop (Stage 8 implemented; full target loop in the architecture doc)

```text
bounded GDC acquisition (anonymous, open access)
        ↓
strict parsing → deterministic science → immutable typed StatisticalState
        ↓
Wide Jev projection + wide question set → validated typed answers
        ↓
Python admission → Candidate (≤3 slots; zero is valid)
        ↓
immutable EvidenceState E0 → registered deterministic action → immutable revision E1/E2
        ↓
Deep Jev projection + deep question set → Python next-move policy
(COMPLETE / FOLLOW_UP / GENERATE_HYPOTHESES / ABSTAIN; recorded, never self-dispatched)
        ↓
optional bounded hypothesis generation → Jev critique (hypothesis question set)
        ↓
Stage 8: final candidate result → authoritative dossier
→ no-Jev comparison → CANDIDATE_COMPLETE → next candidate → RUN_COMPLETED
```

See [architecture](docs/ARCHITECTURE.md) for the full loop including the provisional
Stage 9 target skeleton, and [repository facts](docs/REPOSITORY_FACTS.md) for the
machine-checked schema/projection/question-set/policy versions.

## Run locally

Requires Python 3.12+ and Node.js 20.9+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# Terminal 1 — read API (SQLite schema version in docs/REPOSITORY_FACTS.md)
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd apps/web
npm ci
npm run dev

# Terminal 3 — real bounded open-access sweep (no credentials)
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m cancerjev run --live

# Optional: Wide Jev evaluation (server-side TYPESAFE_API_KEY only)
$env:TYPESAFE_API_KEY="<your TypeSafe key>"
python -m cancerjev run --live --jev

# Optional: one explicitly selected candidate investigation, authorized iteration
python -m cancerjev run --live --jev --deep-candidate TP53 --deep-followup

# Fixture demonstration (offline, synthetic, same engine)
python -m cancerjev run --fixture demo

# Bounded systematic mutation discovery over the fixed indexed universe prefix
python -m cancerjev discover --live

# Bounded anonymous contract capture
python -m cancerjev probe

# Offline baseline-vs-Jev comparison against operator-supplied labels
python -m cancerjev evaluate --run <run-id> --labels <labels.json>
```

Open `http://localhost:3000/runs`. The UI shows deterministic measurements and Jev judgments
in clearly separated panels; the research process never writes through FastAPI.

Configuration: for local development, copy `.env.local.example` to `.env.local` and fill in
the provider keys; `.env.local` is gitignored and loaded automatically by
`cancerjev.config.load_local_env()` (real environment variables win, blank values are
ignored, values are never logged). Set `CANCERJEV_NO_DOTENV=1` to disable. It includes
`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY` (used for optional explicitly authorized OpenRouter
hypothesis generation), the operational `CANCERJEV_*` settings below, and the frontend URL.

- `CANCERJEV_DATA_DIR` — local persistence directory; defaults to `./data`.
- `CANCERJEV_FIXTURE_STAGE_DELAY_MS` — demo-only delay; defaults to `500`, tests use `0`.
- `CANCERJEV_RUN_INTERVAL_MINUTES` — worker interval; defaults to `60`.
- `CANCERJEV_WEB_ORIGIN` — local CORS origin; defaults to `http://localhost:3000`.
- `CANCERJEV_GDC_MAX_REQUESTS` / `CANCERJEV_GDC_MAX_BYTES` / `CANCERJEV_GDC_PER_RESPONSE_BYTES` — application caps; defaults `150`, `64 MiB`, `5 MiB`.
- `CANCERJEV_GDC_CACHE` — set `0` to disable the normalized response cache.
- `CANCERJEV_JEV_MODEL` — pinned model identity; defaults to `jev-1.13.0`.
- `TYPESAFE_API_KEY` — required only for `--jev`; read at call time and never persisted or logged.
- `OPENROUTER_API_KEY` — optional, environment-only; used only by the explicitly authorized CLI hypothesis path.
- `NEXT_PUBLIC_CANCERJEV_API_URL` — browser API URL; defaults to `http://127.0.0.1:8000`.

`--jev` requires `--live`; the fixture path never constructs a live provider. `--deep-candidate`
accepts `gene`, `gene:<SYMBOL>`, `state:<STATE_ID>` or `slot:N` and requires `--live --jev`;
`--deep-followup` authorizes bounded iteration; `--deep-hypotheses` requests bounded generation
without rewriting the recorded next move. Persistence schema is versioned and earlier databases are
explicitly rejected, not automatically migrated or reset (current versions in
`docs/REPOSITORY_FACTS.md`). Retain historical databases and
artifacts; use a separate compatible data directory.

## Open-access guarantees

- One transport owns every GDC request; it has no credential parameter and never constructs
  `Authorization` or `X-Auth-Token`.
- Host, endpoints and methods are allowlisted; `/data`, manifests and file downloads are not
  routable; redirects are refused; responses are size-capped and retained with SHA-256.
- File metadata queries always filter `access=open`; a controlled record fails closed and is
  never admitted to science.
- 401/403 become `UNAVAILABLE_ACCESS` with no retry and no credential lookup.
- Adversarial tests enforce all of the above; live captures record `authentication_headers_sent: []`.

Exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may carry a provider
authorization header for generated hypothesis text; that credential is environment-only, never
persisted or logged, and its output is bounded, validated and never evidence.

## Verification

```powershell
python -m ruff check cancerjev apps tests
python -m pytest                      # offline suite; live markers excluded by default
python -m pytest -m live_gdc          # opt-in bounded live GDC contract probe
python -m pytest -m live_jev          # opt-in live Jev evaluation (needs TYPESAFE_API_KEY)
python -m mypy                        # scoped strict check; not whole-repository typing
python tests/repository_facts.py check  # documentation-facts contract (also pytest-enforced)
```

The date-stamped verification record (offline suite, ruff, mypy, browser acceptance, live
acceptance) lives in [implementation status](docs/IMPLEMENTATION_STATUS.md) and is the only
place claims about what was verified are made. Browser acceptance lives in `tests/browser/`
with its own Playwright config and package, and CI runs it as a separate job. No scientific
readiness, incremental Jev value or production use is claimed.

The default Python suite blocks outbound network connections except loopback test servers. No
default test needs Docker, PostgreSQL, Redis, GDC, TypeSafe/Jev, OpenRouter, or secrets.

## Scope boundary

The registered deep actions check retained evidence integrity or restate held values with
predeclared descriptive methods; they acquire no new data and compute no new biological
measurement. The default hypothesis generator is deterministic; the optional OpenRouter
adapter can make paid model calls only on the authorized CLI path. Jev judgments are semantic
policy inputs, never measurements, significance, or clinical claims. Public GDC evidence alone
does not establish dependency, druggability, therapeutic efficacy, safety, clinical benefit,
biomarker qualification, or drug success; OntoJev's claim boundary is **candidate-target
investigation**, not therapeutic target validation.

Stage 9 (the autonomous multi-modal target-discovery reorientation) is **PROVISIONAL TARGET
ARCHITECTURE, SUBJECT TO THE SOURCE-GROUNDED STAGE 9 DESIGN REVIEWS**; see
[the roadmap](docs/DISCOVERY_ROADMAP.md). Proposed contracts there are not current runtime
behavior. Scientific contracts live in `docs/`.

See [architecture](docs/ARCHITECTURE.md), [domain models](docs/DOMAIN_MODELS.md),
[persistence](docs/PERSISTENCE.md), [scientific invariants](docs/SCIENTIFIC_INVARIANTS.md),
[research loop](docs/RESEARCH_LOOP.md), [run events](docs/RUN_EVENTS.md),
[GDC strategy](docs/GDC_STRATEGY.md), [GDC budgets](docs/GDC_BUDGETS.md),
[GDC discovery captures](docs/GDC_DISCOVERY_CAPTURES.md), [source review](docs/SOURCE_REVIEW.md),
[Jev design](docs/JEV_DESIGN.md), [question architecture](docs/JEV_QUESTIONS.md),
[API contract](docs/API_CONTRACT.md), [UI spec](docs/UI_SPEC.md),
[testing contract](docs/TESTING.md), [development skills](docs/DEVELOPMENT_SKILLS.md),
[repository facts](docs/REPOSITORY_FACTS.md),
[implementation status](docs/IMPLEMENTATION_STATUS.md),
[deployment portability](docs/DEPLOYMENT_PORTABILITY.md) and the
[discovery roadmap](docs/DISCOVERY_ROADMAP.md).
