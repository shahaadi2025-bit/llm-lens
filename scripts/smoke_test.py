"""Post-deploy smoke test, standard library only (works on Windows, macOS, Linux).
Usage:  python scripts/smoke_test.py https://your-app.onrender.com
Creates one small demo experiment (and a follow-up if an anomaly is flagged). Exit code 0 = all passed."""
import json
import random
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
FAILED = 0


def show(ok: bool, msg: str) -> None:
    global FAILED
    FAILED += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + msg, flush=True)


def call(method: str, path: str, body: dict | None = None, timeout: int = 150):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and r.headers.get("content-type", "").startswith("application/json") else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300]


def wait_done(eid: str):
    for _ in range(90):
        _, e = call("GET", f"/api/experiments/{eid}")
        if e["status"] in ("completed", "failed", "cancelled"):
            return e
        time.sleep(2)
    raise TimeoutError(eid)


def main() -> int:
    print(f"Smoke test against {BASE} (the first request can take about a minute on free hosting)")
    code, h = call("GET", "/api/health")
    show(code == 200 and h["database"] == "ok", f"health: status {h.get('status')}, database {h.get('database')}, mock {h.get('mock_mode')}")
    code, page = call("GET", "/")
    show(code == 200 and b"LLM Lens" in page, "website loads")
    code, _ = call("GET", "/api/failures")
    show(code == 200, "current API version deployed")
    seed = random.randint(1, 10**6)
    code, e = call("POST", "/api/experiments", {"name": f"smoke {seed}", "task_type": "arithmetic_representation", "seed": seed,
                                                 "config": {"n_random_pairs": 5}})
    show(code == 201 and e["counts"]["total"] == 36, f"experiment created ({code})")
    if code != 201:
        return 1
    call("POST", f"/api/experiments/{e['id']}/run")
    done = wait_done(e["id"])
    show(done["status"] == "completed", f"run {done['status']}: {done['counts']['succeeded']}/{done['counts']['total']} runs")
    _, ms = call("GET", f"/api/experiments/{e['id']}/metrics")
    acc = next((m for m in ms if m["name"] == "accuracy"), None)
    show(bool(acc) and acc["evidence_runs"] == acc["n"], f"accuracy {acc['value']:.1%} CI [{acc['ci_low']:.1%}, {acc['ci_high']:.1%}] n={acc['n']}, traceable to {acc['evidence_runs']} runs" if acc else "no accuracy metric")
    code, rep = call("POST", "/api/reports", {"experiment_id": e["id"]})
    show(code == 201 and rep["content"].count("\n## ") == 14, f"research report generated ({code})")
    code, csvdata = call("GET", f"/api/exports/experiments/{e['id']}/runs.csv")
    show(code == 200 and csvdata.count(b"\n") >= 37, "runs CSV export")
    _, fl = call("GET", f"/api/failures?experiment_id={e['id']}&label=representation_sensitivity")
    if fl:
        code, child = call("POST", f"/api/experiments/{e['id']}/follow-up", {"failure_id": fl[0]["id"]})
        show(code == 201, f"follow-up created from anomaly ({code})")
        if code == 201:
            call("POST", f"/api/experiments/{child['id']}/run")
            wait_done(child["id"])
            _, x = call("GET", f"/api/failures/{fl[0]['id']}/explain")
            show(x["failure"]["status"] in ("reproduced", "not_reproduced"), f"verdict: {x['failure']['status']} ({x['evidence']['level']}/{x['evidence']['strength']})")
    else:
        print("      (no anomaly flagged this time; the mock only errs ~15%; rerun to exercise follow-ups)")
    print("\nALL PASSED" if not FAILED else f"\n{FAILED} CHECK(S) FAILED")
    return 1 if FAILED else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  {type(exc).__name__}: {exc}")
        sys.exit(1)
