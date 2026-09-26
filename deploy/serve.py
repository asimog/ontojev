"""Container entrypoint: bootstrap storage, optionally seed demo data, serve.

This is deployment tooling, not science. The API is read-only. When
``CANCERJEV_RUN_WORKER=1`` the canonical durable worker starts alongside it and
shares the same data directory: it observes the release once per cycle, records
PROGRAM_IDLE while no campaign profile is validated for autonomous use, and
never runs an unpromoted campaign. Seeding runs the offline synthetic fixture,
which is labelled FAKE throughout the UI and records zero provider usage.
"""

from __future__ import annotations

import os
import subprocess
import sys

DEMO_MARKER = ".demo-seeded"


def seed_demo_data() -> None:
    data_dir = os.environ.get("CANCERJEV_DATA_DIR", "/data")
    marker = os.path.join(data_dir, DEMO_MARKER)
    if os.environ.get("CANCERJEV_SEED_DEMO", "0") != "1" or os.path.exists(marker):
        return
    os.makedirs(data_dir, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "cancerjev", "run", "--fixture", "demo"],
        check=True,
        env={**os.environ, "CANCERJEV_FIXTURE_STAGE_DELAY_MS": "0"},
    )
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("synthetic demo data seeded\n")


def start_worker() -> None:
    """Start the durable program worker when the deployment declares it."""
    if os.environ.get("CANCERJEV_RUN_WORKER", "0") != "1":
        return
    subprocess.Popen(
        [sys.executable, "-m", "cancerjev", "worker", "--live"],
        env={**os.environ, "CANCERJEV_NO_DOTENV": "1"},
    )


def main() -> None:
    os.environ.setdefault("CANCERJEV_FIXTURE_STAGE_DELAY_MS", "0")
    seed_demo_data()
    start_worker()
    port = os.environ.get("PORT", "8080")
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "apps.api.main:create_app",
        "--factory", "--host", "0.0.0.0", "--port", port,
    ])


if __name__ == "__main__":
    main()
