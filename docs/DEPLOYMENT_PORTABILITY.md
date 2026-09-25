# Local runtime and portability boundary

Status: the current local single-machine runtime, settings and schema behavior described here are
IMPLEMENTED. Backup automation, retention and any dedicated future infrastructure are PLANNED;
cloud portability is UNVERIFIED and has no adapter.

Required: Python 3.12+, Node.js satisfying the chosen stable Next.js engine requirement, npm, and
local disk. The implemented Python runtime uses pinned dependency ranges in `pyproject.toml`; the
presence of an older/newer local toolchain does not change the supported floor. CI pins Python
3.12 and Node 22.

One research process runs the CLI loop. One FastAPI process serves reads. One Next.js process
serves UI. “One Python research process” does not mean embedding web serving or spawning
background research from FastAPI reload hooks. API restarts never create runs. `apps/web/` is not
part of the Stage 3 hard cutover; browser acceptance lives in `tests/browser/` with its own
Playwright configuration and runs in CI.

Settings are environment-based: `CANCERJEV_DATA_DIR` (absolute), `CANCERJEV_WEB_ORIGIN`,
`NEXT_PUBLIC_CANCERJEV_API_URL`, `CANCERJEV_RUN_INTERVAL_MINUTES`,
`CANCERJEV_GDC_MAX_REQUESTS`/`_MAX_BYTES`/`_PER_RESPONSE_BYTES`/`_CACHE`, `CANCERJEV_JEV_MODEL`,
and `TYPESAFE_API_KEY` (server-only, Jev only). For local development these may be placed in a
gitignored `.env.local` (template: `.env.local.example`), which
`cancerjev.config.load_local_env()` loads only for names the real environment does not define;
`OPENROUTER_API_KEY` is read by the CLI for optional authorized hypothesis generation using the
implemented adapter. Generation defaults to deterministic behavior. The documentation pass made
no paid calls. There is deliberately **no GDC key**: the GDC transport is anonymous and
open-access by invariant. Fixture mode is offline, runs the same shared orchestrator with fixture
doubles, and rejects live provider construction; `--jev` requires `--live`.

SQLite is schema 5; older databases are refused, not migrated. Reset by stopping the research
process and the API, then moving or deleting the whole data directory (including WAL files and
`research.lock`); bootstrap creates a fresh database. There are no migrations and no legacy
readers.

No Postgres, Redis, Celery, Docker, Supabase, Vercel/Railway code, S3/MinIO, WebSockets,
microservices, distributed workers or generic workflow engine is used. The implemented vertical
slice has no demonstrated need for any of them. Also do not build accounts/OAuth/RBAC, billing,
Kubernetes/Kafka, vector DB/RAG/literature search, blockchain, mobile app, raw
sequencing/BAM/VCF acquisition, scRNA pipeline, complex evidence graph, clinical workflow or
treatment recommendations.

SQLite WAL and OS file ownership assume a single local machine with reliable local filesystem
semantics, not shared NFS/network drives or multiple hosts. Filesystem portability is addressed
through `pathlib` and cross-platform process locking. No cloud migration adapters are implemented
speculatively. Future infrastructure changes require a demonstrated workload need and a separate
design, keeping scientific/domain code independent.

Future backup should preserve a consistent SQLite backup plus all referenced immutable artifacts;
copying only a live `.db` while ignoring WAL is insufficient. Backup automation and retention are
not implemented; document disk use so continuous local runs remain inspectable.