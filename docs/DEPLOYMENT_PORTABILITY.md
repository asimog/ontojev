# Local runtime and portability boundary

Required after approval: Python 3.12+, Node.js satisfying the chosen stable Next.js engine requirement, npm, and local disk. Pin exact package versions during Phase 1; documentation does not pretend a version was installed here.

One research process runs the CLI loop. One FastAPI process serves reads. One Next.js process serves UI. “One Python research process” does not mean embedding web serving or spawning background research from FastAPI reload hooks. API restarts never create runs.

Settings are environment-based: `CANCERJEV_DATA_DIR` (absolute), `CANCERJEV_API_URL`, `NEXT_PUBLIC_CANCERJEV_API_URL`, `CANCERJEV_RUN_INTERVAL_MINUTES`, and documented budget variables. Use one data directory rather than an unused generalized database URL in Phase 1. Future provider keys are server-only; there is no GDC key. Fake mode is the only implemented mode in Phase 1 and rejects live flags.

No Postgres, Redis, Celery, Docker, Supabase, Vercel/Railway code, S3/MinIO, WebSockets, microservices, distributed workers or generic workflow engine. The fake vertical slice has no demonstrated need for any of them. Also do not build accounts/OAuth/RBAC, billing, Kubernetes/Kafka, vector DB/RAG/literature search, blockchain, mobile app, raw sequencing/BAM/VCF acquisition, scRNA pipeline, complex evidence graph, clinical workflow or treatment recommendations.

SQLite WAL and OS file ownership assume a single local machine with reliable local filesystem semantics, not shared NFS/network drives or multiple hosts. Filesystem portability is addressed through pathlib and cross-platform process locking. No cloud migration adapters are implemented speculatively. Future infrastructure changes require a demonstrated workload need and a separate design, keeping scientific/domain code independent.

Future backup should preserve a consistent SQLite backup plus all referenced immutable artifacts; copying only a live .db while ignoring WAL is insufficient. Backup automation and retention are deferred beyond the fake slice; document disk use so continuous local runs remain inspectable.
