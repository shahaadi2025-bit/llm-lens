"""Performance benchmark: seeds a temporary SQLite database through the real API, then measures endpoint latency and
SQL statements per request, plus engine throughput. In-process (no network), so numbers show application cost only.

Run from the backend folder:   python ../scripts/benchmark.py [n_experiments]
SQLite is NOT PostgreSQL: use these numbers to find N+1 queries and relative cost, not as production figures.
"""
import asyncio
import os
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

N_EXPERIMENTS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
tmp = Path(tempfile.mkdtemp()) / "bench.sqlite"
os.environ.update(DATABASE_URL=f"sqlite+aiosqlite:///{tmp}", MODEL_PROVIDER="mock", SECRET_KEY="b" * 40, APP_ENV="test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.api.deps import get_engine  # noqa: E402
from app.core.db import dispose_engine, get_engine as get_db_engine  # noqa: E402
from app.main import create_app  # noqa: E402

STATEMENTS = 0


async def timed(c: httpx.AsyncClient, method: str, path: str, repeat: int = 7, **kw):
    global STATEMENTS
    samples, counts = [], []
    for _ in range(repeat):
        before = STATEMENTS
        t = time.perf_counter()
        r = await c.request(method, path, **kw)
        samples.append((time.perf_counter() - t) * 1000)
        counts.append(STATEMENTS - before)
        assert r.status_code < 400, (path, r.status_code, r.text[:200])
    samples.sort()
    return statistics.median(samples), samples[int(len(samples) * 0.9) - 1] if len(samples) > 1 else samples[0], counts[-1]


async def main() -> None:
    global STATEMENTS
    cfg = Config(str(Path(__file__).resolve().parents[1] / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "backend" / "alembic"))
    await asyncio.to_thread(command.upgrade, cfg, "head")
    app = create_app()
    engine = get_db_engine()

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _count(*_a):  # noqa: ANN002
        global STATEMENTS
        STATEMENTS += 1

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bench", timeout=120) as c:
        await c.get("/api/models")
        eng = get_engine()
        t0 = time.perf_counter()
        ids = []
        for i in range(N_EXPERIMENTS):
            kind = "arithmetic_representation" if i % 2 == 0 else "prompt_sensitivity"
            model = "mock-deterministic-v1" if i % 4 < 2 else "mock-deterministic-v2"
            r = await c.post("/api/experiments", json={"name": f"bench {i}", "task_type": kind, "seed": i, "model_slug": model,
                                                       "config": {"n_random_pairs": 3 if kind == "prompt_sensitivity" else 5}})
            ids.append(r.json()["id"])
        total_runs = 0
        for eid in ids:
            await c.post(f"/api/experiments/{eid}/run")
            await eng.wait(uuid.UUID(eid))
        elapsed = time.perf_counter() - t0
        counts = [(await c.get(f"/api/experiments/{e}")).json()["counts"] for e in ids]
        total_runs = sum(k["succeeded"] for k in counts)
        print(f"engine: {N_EXPERIMENTS} experiments ({total_runs} runs) created+run+analysed in {elapsed:.1f}s "
              f"= {N_EXPERIMENTS / elapsed * 60:.0f} experiments/min, {total_runs / elapsed:.0f} runs/s (mock model, SQLite)")
        failed = sum(k["failed"] for k in counts)
        print(f"engine: failed runs {failed} (failure rate {failed / max(total_runs, 1):.1%})")

        failures = (await c.get("/api/failures", params={"limit": 50})).json()
        a, b = ids[0], ids[1]
        mv = {v["model_slug"]: v["id"] for v in (await c.get("/api/model-versions")).json()}
        model_id = (await c.get("/api/models")).json()[0]["id"]
        rows = [
            ("GET /experiments (25)", "GET", "/api/experiments"),
            ("GET /experiments?limit=100", "GET", "/api/experiments?limit=100"),
            ("GET /dashboard", "GET", "/api/dashboard"),
            ("GET /experiments/{id}", "GET", f"/api/experiments/{a}"),
            ("GET /experiments/{id}/metrics", "GET", f"/api/experiments/{a}/metrics"),
            ("GET /experiments/{id}/analysis", "GET", f"/api/experiments/{a}/analysis"),
            ("GET /failures (50)", "GET", "/api/failures?limit=50"),
            ("GET /failures/{id}/explain", "GET", f"/api/failures/{failures[0]['id']}/explain" if failures else "/api/health"),
            ("GET /failure-clusters", "GET", "/api/failure-clusters"),
            ("GET /fingerprints/{model}", "GET", f"/api/fingerprints/{model_id}"),
            ("GET /compare", "GET", f"/api/compare?a={mv['mock-deterministic-v1']}&b={mv['mock-deterministic-v2']}"),
            ("GET /exports/.../runs.csv", "GET", f"/api/exports/experiments/{a}/runs.csv"),
            ("GET /exports/experiments.csv", "GET", "/api/exports/experiments.csv"),
        ]
        print(f"\n{'endpoint':36} {'p50 ms':>8} {'p90 ms':>8} {'SQL stmts':>10}")
        for name, m, p in rows:
            p50, p90, n = await timed(c, m, p)
            print(f"{name:36} {p50:8.1f} {p90:8.1f} {n:10d}")
        for name, m, p, repeat in (("POST /failure-clusters/recompute", "POST", "/api/failure-clusters/recompute", 3),
                                   ("POST /reports (experiment)", "POST", "/api/reports", 3)):
            kw = {"json": {"experiment_id": a}} if "reports" in p else {}
            p50, p90, n = await timed(c, m, p, repeat=repeat, **kw)
            print(f"{name:36} {p50:8.1f} {p90:8.1f} {n:10d}")
    await dispose_engine()


asyncio.run(main())
