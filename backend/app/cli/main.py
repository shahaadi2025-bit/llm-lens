"""llm-lens command line. Talks to any LLM Lens server over HTTP (local or public), or runs fully in-process with --local
(own SQLite database, no server needed)."""
import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from app.cli.templates import TemplateError, load_template

TOKEN_FILE = Path.home() / ".llm-lens" / "token"
BACKEND_DIR = Path(__file__).resolve().parents[2]


class CliError(Exception):
    pass


def _token(args: argparse.Namespace) -> str | None:
    if args.token:
        return str(args.token)
    if os.environ.get("LLM_LENS_TOKEN"):
        return os.environ["LLM_LENS_TOKEN"]
    try:
        return TOKEN_FILE.read_text().strip() or None
    except OSError:
        return None


def _migrate() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def open_client(args: argparse.Namespace) -> AsyncIterator[httpx.AsyncClient]:
    headers = {"Authorization": f"Bearer {t}"} if (t := _token(args)) else {}
    if args.local:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(args.db).resolve()}"
        from app.api.deps import get_adapter, get_engine
        from app.core.config import get_settings
        from app.core.db import dispose_engine
        from app.main import create_app

        for fn in (get_settings, get_adapter, get_engine):
            fn.cache_clear()
        await asyncio.to_thread(_migrate)
        app = create_app()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local", headers=headers,
                                         timeout=300) as c:
                yield c
        finally:
            await dispose_engine()
    else:
        async with httpx.AsyncClient(base_url=args.api.rstrip("/"), headers=headers, timeout=120) as c:
            yield c


async def call(c: httpx.AsyncClient, method: str, path: str, **kw: Any) -> httpx.Response:
    try:
        r = await c.request(method, f"/api{path}", **kw)
    except httpx.HTTPError as exc:
        raise CliError(f"cannot reach the server ({type(exc).__name__}). Is it running? Use --api URL or --local.") from exc
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise CliError(f"{r.status_code}: {detail}")
    return r


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def banner(demo: bool) -> None:
    if demo:
        print("*** DEMO / MOCK DATA: produced by a mock model; not real LLM evidence. ***")


async def cmd_health(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    h = (await call(c, "GET", "/health")).json()
    print(f"status: {h['status']}  database: {h['database']}  version: {h['version']}  env: {h['environment']}")
    print(f"model: {h['model_provider']} / {h['model_name']}  mock mode: {h['mock_mode']}  public demo: {h['public_demo_mode']}")
    banner(h["mock_mode"])
    return 0 if h["status"] == "ok" else 1


async def wait_done(c: httpx.AsyncClient, exp_id: str, quiet: bool) -> dict[str, Any]:
    last = -1
    while True:
        e = (await call(c, "GET", f"/experiments/{exp_id}")).json()
        done = e["counts"]["succeeded"] + e["counts"]["failed"]
        if not quiet and done != last:
            print(f"  {done}/{e['counts']['total']} runs finished ({e['status']})", flush=True)
            last = done
        if e["status"] in ("completed", "failed", "cancelled"):
            return e  # type: ignore[no-any-return]
        await asyncio.sleep(0.5)


async def print_summary(c: httpx.AsyncClient, e: dict[str, Any]) -> None:
    print(f"experiment {e['id']}: {e['name']}  [{e['status']}]  model {e['model_slug']}")
    banner(e["is_demo_data"])
    ms = (await call(c, "GET", f"/experiments/{e['id']}/metrics")).json()
    for m in ms:
        if m["name"] == "accuracy":
            print(f"  accuracy {pct(m['value'])}  95% CI [{pct(m['ci_low'])}, {pct(m['ci_high'])}]  n={m['n']}  ({m['method']})")
    fl = (await call(c, "GET", "/failures", params={"experiment_id": e["id"], "label": "representation_sensitivity"})).json()
    if fl:
        print(f"  {len(fl)} potential anomalies flagged (flags are questions, not verdicts); see: llm-lens inspect {e['id']}")
    if e.get("error"):
        print(f"  note: {e['error']}")


async def cmd_run(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    body = load_template(args.template)
    e = (await call(c, "POST", "/experiments", json=body)).json()
    print(f"created {e['id']} ({e['counts']['total']} runs)")
    await call(c, "POST", f"/experiments/{e['id']}/run")
    if args.no_wait:
        print(f"started; check with: llm-lens inspect {e['id']}")
        return 0
    final = await wait_done(c, e["id"], quiet=False)
    await print_summary(c, final)
    if args.report:
        await write_report(c, final["id"], args.report)
    return 0 if final["status"] == "completed" else 1


async def cmd_list(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    params: dict[str, Any] = {"limit": args.limit}
    if args.status:
        params["status"] = args.status
    rows = (await call(c, "GET", "/experiments", params=params)).json()
    if not rows:
        print("no experiments")
        return 0
    print(f"{'ID':36}  {'STATUS':9}  {'RUNS':>7}  {'CORRECT':>7}  NAME")
    for e in rows:
        k = e["counts"]
        mock = " [DEMO]" if e["is_demo_data"] else ""
        print(f"{e['id']:36}  {e['status']:9}  {k['succeeded']:>3}/{k['total']:<3}  {k['passed']:>7}  {e['name']}{mock}")
    return 0


async def cmd_inspect(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    e = (await call(c, "GET", f"/experiments/{args.id}")).json()
    print(f"{e['name']}  [{e['status']}]")
    banner(e["is_demo_data"])
    print(f"question: {e['research_question']}")
    print(f"model {e['model_slug']} ({e['model_version']})  evaluator {e['evaluator']}  seed {e['seed']}  "
          f"temperature {e['temperature']}  repetitions {e['repetitions']}")
    await print_summary(c, e)
    if args.runs:
        print("\nruns:")
        for r in e["runs"]:
            v = "correct" if (r["evaluation"] and r["evaluation"]["passed"]) else ("incorrect" if r["evaluation"] else r["status"])
            got = (r["response"] or "")[:40]
            print(f"  #{r['run_index']:<3} {v:9} {r['variant_label']:28} expected {r['expected_answer']}  got {got!r}")
    return 0


async def resolve_version(c: httpx.AsyncClient, ref: str) -> str:
    versions = (await call(c, "GET", "/model-versions")).json()
    for v in versions:
        if ref in (v["id"], f"{v['model_slug']}@{v['version_label']}", v["model_slug"]):
            return str(v["id"])
    names = ", ".join(f"{v['model_slug']}@{v['version_label']}" for v in versions)
    raise CliError(f"unknown model version {ref!r}. Available: {names or 'none'}")


async def cmd_compare(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    a, b = await resolve_version(c, args.a), await resolve_version(c, args.b)
    r = (await call(c, "GET", "/compare", params={"a": a, "b": b})).json()
    print(f"A = {r['a_label']}   B = {r['b_label']}")
    banner(r["includes_demo_data"])
    if not r["comparable"]:
        print("not comparable: no completed experiments with an identical design on both versions.")
        print("run the same template on both models (same seed and config), then compare again.")
        return 1
    print(f"{len(r['matched'])} matched experiment pair(s)")
    for d in r["differences"]:
        print(f"- {d['statement']}")
        print(f"    A {pct(d['a_value'])} (n={d['a_n']})  B {pct(d['b_value'])} (n={d['b_n']})  Cohen's h {d['cohens_h']:.2f}")
    for n in r["notes"]:
        print(f"note: {n}")
    return 0


async def write_report(c: httpx.AsyncClient, exp_id: str, out: str | None) -> None:
    rep = (await call(c, "POST", "/reports", json={"experiment_id": exp_id})).json()
    text = (await call(c, "GET", f"/reports/{rep['id']}/download")).text
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"report written to {out}")
    else:
        print(text)


async def cmd_report(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    await write_report(c, args.id, args.output)
    return 0


async def cmd_export(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    path = f"/exports/experiments/{args.id}.json" if args.format == "json" else f"/exports/experiments/{args.id}/runs.csv"
    text = (await call(c, "GET", path)).text
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"written to {args.output}")
    else:
        print(text)
    return 0


async def cmd_login(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    email = input("email: ").strip()
    password = getpass.getpass("password: ")
    r = (await call(c, "POST", "/auth/login", json={"email": email, "password": password})).json()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(r["token"])
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    print(f"signed in as {r['user']['email']}; token saved to {TOKEN_FILE} (expires in about 12 hours)")
    return 0


DEMO_PREFIX = "Demo: "


async def _create_and_run(c: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any] | None:
    try:
        e = (await call(c, "POST", "/experiments", json=body)).json()
    except CliError as exc:
        if str(exc).startswith("409"):
            return None  # an identical demo experiment already exists
        raise
    await call(c, "POST", f"/experiments/{e['id']}/run")
    return await wait_done(c, e["id"], quiet=True)


async def cmd_seed_demo(c: httpx.AsyncClient, args: argparse.Namespace) -> int:
    """Populate a mock-mode installation with a small deterministic dataset so every page has something to show.
    Everything it creates runs on the mock model and is labelled DEMO / MOCK DATA; it is never real LLM evidence."""
    h = (await call(c, "GET", "/health")).json()
    if not h["mock_mode"]:
        raise CliError("demo data is generated by the mock model, so it is only seeded on mock deployments (MODEL_PROVIDER=mock).")
    await call(c, "GET", "/models")  # registers the mock model versions
    specs: list[dict[str, Any]] = [
        {"name": f"{DEMO_PREFIX}arithmetic forms, model A", "task_type": "arithmetic_representation", "model_slug": "mock-deterministic-v1",
         "seed": 11, "config": {"n_random_pairs": 5}},
        {"name": f"{DEMO_PREFIX}arithmetic forms, model B", "task_type": "arithmetic_representation", "model_slug": "mock-deterministic-v2",
         "seed": 11, "config": {"n_random_pairs": 5}},
        {"name": f"{DEMO_PREFIX}prompt sensitivity, model A", "task_type": "prompt_sensitivity", "model_slug": "mock-deterministic-v1",
         "seed": 4, "config": {"n_random_pairs": 3}},
        {"name": f"{DEMO_PREFIX}instruction ordering, model A", "task_type": "instruction_ordering",
         "model_slug": "mock-deterministic-v1", "seed": 3, "max_tokens": 160, "config": {"n_tasks": 10}},
        {"name": f"{DEMO_PREFIX}context position, model A", "task_type": "context_position",
         "model_slug": "mock-deterministic-v1", "seed": 6, "max_tokens": 32, "config": {"size_tokens": 1500, "n_trials": 3}},
        {"name": f"{DEMO_PREFIX}context length, model A", "task_type": "context_length", "model_slug": "mock-deterministic-v1",
         "seed": 8, "max_tokens": 32, "config": {"sizes_tokens": [500, 1000, 2000, 3000], "n_trials": 3}},
    ]
    made = []
    for spec in specs:
        e = await _create_and_run(c, spec)
        print(("created  " if e else "exists   ") + str(spec["name"]))
        if e:
            made.append(e)
    if not made:
        print("demo data already present; nothing to do")
        return 0
    b = next((e for e in made if "model B" in e["name"]), made[0])
    fl = (await call(c, "GET", "/failures", params={"experiment_id": b["id"], "label": "representation_sensitivity"})).json()
    if fl:
        child = (await call(c, "POST", f"/experiments/{b['id']}/follow-up", json={"failure_id": fl[0]["id"]})).json()
        await call(c, "POST", f"/experiments/{child['id']}/run")
        await wait_done(c, child["id"], quiet=True)
        print(f"created  follow-up experiment from a flagged anomaly ({child['name']})")
    clusters = (await call(c, "POST", "/failure-clusters/recompute")).json()
    print(f"clustered incorrect answers into {len(clusters)} cluster(s)")
    await call(c, "POST", "/reports", json={"experiment_id": b["id"]})
    print("generated a research report")
    banner(True)
    print("done: open the Dashboard, Failure analysis, Fingerprint and Compare pages.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-lens", description="LLM Lens: black-box LLM behavioral experiments.")
    p.add_argument("--api", default=os.environ.get("LLM_LENS_API", "http://localhost:8000"), help="server URL (env LLM_LENS_API)")
    p.add_argument("--token", help="access token (env LLM_LENS_TOKEN, or saved by `llm-lens login`)")
    p.add_argument("--local", action="store_true", help="run in-process with its own SQLite database; no server needed")
    p.add_argument("--db", default="lens-cli.sqlite", help="SQLite file used with --local")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("health", help="check the server").set_defaults(fn=cmd_health)
    r = sub.add_parser("run", help="run an experiment from a YAML template")
    r.add_argument("template")
    r.add_argument("--no-wait", action="store_true")
    r.add_argument("--report", metavar="FILE", help="also write a Markdown research report")
    r.set_defaults(fn=cmd_run)
    ls = sub.add_parser("list", help="list experiments")
    ls.add_argument("--status")
    ls.add_argument("--limit", type=int, default=25)
    ls.set_defaults(fn=cmd_list)
    i = sub.add_parser("inspect", help="show an experiment with metrics and anomalies")
    i.add_argument("id")
    i.add_argument("--runs", action="store_true", help="also list every run")
    i.set_defaults(fn=cmd_inspect)
    cm = sub.add_parser("compare", help="compare two model versions (id, slug or slug@version)")
    cm.add_argument("a")
    cm.add_argument("b")
    cm.set_defaults(fn=cmd_compare)
    rp = sub.add_parser("report", help="generate a Markdown research report for an experiment")
    rp.add_argument("id")
    rp.add_argument("-o", "--output", metavar="FILE")
    rp.set_defaults(fn=cmd_report)
    ex = sub.add_parser("export", help="export an experiment as JSON or CSV")
    ex.add_argument("id")
    ex.add_argument("--format", choices=["json", "csv"], default="json")
    ex.add_argument("-o", "--output", metavar="FILE")
    ex.set_defaults(fn=cmd_export)
    sub.add_parser("login", help="sign in and save a token").set_defaults(fn=cmd_login)
    sub.add_parser("seed-demo", help="fill a mock-mode installation with a small DEMO dataset (5 types)").set_defaults(
        fn=cmd_seed_demo)
    return p


async def _run(args: argparse.Namespace) -> int:
    async with open_client(args) as c:
        return int(await args.fn(c, args))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (CliError, TemplateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
