import csv
import io
import re
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import Experiment
from app.reports.experiment_report import build_experiment_report
from app.reports.markdown_utils import md_code, md_text, table
from app.services.adapters.base import GenerationRequest, GenerationResult
from app.services.adapters.mock import MockAdapter
from app.services.exports import csv_safe, experiment_bundle, runs_csv, safe_filename
from tests.test_engine import make as make_engine_experiment

PW = "correct horse battery"
BODY = {"name": "arith", "task_type": "arithmetic_representation", "seed": 3, "config": {"n_random_pairs": 11},
        "model_slug": "mock-deterministic-v2"}
SECTIONS = ["Research question", "Hypothesis", "Methodology", "Model", "Dataset", "Experimental configuration", "Results",
            "Statistical analysis", "Failure cases", "Potential explanations", "Alternative explanations", "Limitations",
            "Reproducibility information", "Conclusion"]


async def signup(client, email):
    r = await client.post("/api/auth/register", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def make(client, headers=None, **over):
    r = await client.post("/api/experiments", json={**BODY, **over}, headers=headers)
    assert r.status_code == 201, r.text
    await client.post(f"/api/experiments/{r.json()['id']}/run", headers=headers)
    await client.app_engine.wait(uuid.UUID(r.json()["id"]))
    return r.json()


async def report(client, exp_id, headers=None):
    r = await client.post("/api/reports", json={"experiment_id": exp_id}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_report_has_all_14_sections_in_order_and_labels_mock_data(client):
    exp = await make(client)
    rep = await report(client, exp["id"])
    heads = re.findall(r"^## (\d+)\. (.+)$", rep["content"], re.M)
    assert [h[1] for h in heads] == SECTIONS and [int(h[0]) for h in heads] == list(range(1, 15))
    assert rep["includes_demo_data"] is True and "DEMO / MOCK DATA" in rep["content"].split("## 1.")[0]
    assert "mock model and is not a finding about any real language model" in rep["content"]


async def test_report_numbers_match_the_stored_metrics_and_have_traceable_ids(client):
    exp = await make(client)
    rep = await report(client, exp["id"])
    acc = next(m for m in (await client.get(f"/api/experiments/{exp['id']}/metrics")).json() if m["name"] == "accuracy")
    assert f"{acc['value'] * 100:.1f}%" in rep["content"] and f"[{acc['ci_low'] * 100:.1f}%, {acc['ci_high'] * 100:.1f}%]" in rep["content"]
    assert "| accuracy |" in rep["content"] and "wilson-95" in rep["content"] and exp["id"] in rep["content"]


async def test_report_never_asserts_causes_or_mechanisms(client):
    exp = await make(client)
    content = (await report(client, exp["id"]))["content"].lower()
    for banned in ("because", "caused by", "due to", "proves", "attention mechanism", "neuron", "the model learned"):
        assert banned not in content, banned
    assert "no supported conclusion about the model's internal mechanisms" in content
    levels = set(re.findall(r"\[(observation|correlation|hypothesis|supported_conclusion)\]", content))
    assert "supported_conclusion" not in levels and levels  # the generator never awards 'supported conclusion'


async def test_small_samples_are_not_interpreted(client):
    exp = await make(client, config={"n_random_pairs": 2}, seed=8)  # 3 problems: far below the 10 needed
    content = (await report(client, exp["id"]))["content"]
    assert "too small to say whether prompt form matters" in content and "fewer than 10" in content


async def test_followup_that_reproduces_is_reported_as_association_not_cause(client):
    exp = await make(client)
    f = (await client.get("/api/failures", params={"experiment_id": exp["id"], "label": "representation_sensitivity"})).json()
    assert f
    child = (await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": f[0]["id"]})).json()
    await client.post(f"/api/experiments/{child['id']}/run")
    await client.app_engine.wait(uuid.UUID(child["id"]))
    status = (await client.get(f"/api/failures/{f[0]['id']}/explain")).json()["failure"]["status"]
    content = (await report(client, exp["id"]))["content"]
    if status == "reproduced":
        assert "reproduced association" in content and "not an identified cause" in content
    else:
        assert "did not reproduce" in content
    assert "## 10. Potential explanations" in content


def test_markdown_text_is_neutralised():
    assert md_text("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert md_text("a | b\nc") == "a \\| b c" and "`" not in md_text("`x`") and len(md_text("x" * 999, 50)) <= 51
    assert md_code("") == "*(empty)*" and md_code("`;|").count("|") == 0 or "\\|" in md_code("`;|")
    assert table(["a"], []) == "*(none)*\n"


class Evil(MockAdapter):
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(text='=HYPERLINK("http://evil")<img src=x onerror=alert(1)> | `tick` \nnewline', finish_reason="stop")


async def test_hostile_model_output_cannot_break_reports_or_csv(engine):
    sm, eng, eid = await make_engine_experiment(engine, Evil())
    await eng.execute(eid)
    async with sm() as s:
        exp = await s.get(Experiment, eid)
        _, md, _ = await build_experiment_report(s, exp)
        assert "<img" not in md and "<script" not in md
        for line in md.splitlines():  # no table row was split by the response text
            if line.startswith("| potential") or line.startswith("| accuracy"):
                assert line.endswith("|")
        data = await runs_csv(s, exp)
        rows = list(csv.reader(io.StringIO(data)))
        assert rows[0][0] == "run_index" and len(rows) == 7
        resp_col = rows[0].index("response")
        assert all(not r[resp_col].startswith("=") for r in rows[1:])  # formula neutralised
        assert rows[1][resp_col].startswith("'=")
        bundle = await experiment_bundle(s, exp)
        assert bundle["export"]["contains_demo_data"] is True and len(bundle["runs"]) == 6


def test_csv_safe_and_filenames():
    assert [csv_safe(x) for x in ("=1+1", "+1", "-1", "@a", "\tx", "ok", 5, None)] == ["'=1+1", "'+1", "'-1", "'@a", "'\tx", "ok", 5, None]
    assert "/" not in safe_filename("../../etc/passwd", "csv") and safe_filename("", "md") == "export.md"
    assert safe_filename("A report: v1!", "md") == "A_report_v1.md"


async def test_private_reports_are_invisible_and_follow_experiment_visibility(client):
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    exp = await make(client, alice)
    rep = await report(client, exp["id"], alice)
    for headers in (bob, None):
        assert (await client.get(f"/api/reports/{rep['id']}", headers=headers)).status_code == 404
        assert (await client.get(f"/api/reports/{rep['id']}/download", headers=headers)).status_code == 404
        assert (await client.get("/api/reports", headers=headers)).json() == []
        assert (await client.post("/api/reports", json={"experiment_id": exp["id"]}, headers=headers)).status_code == 404
    await client.patch(f"/api/experiments/{exp['id']}", json={"is_public": True}, headers=alice)
    assert (await client.get(f"/api/reports/{rep['id']}", headers=bob)).status_code == 200
    assert [r["id"] for r in (await client.get("/api/reports", headers=None)).json()] == [rep["id"]]
    assert (await client.delete(f"/api/reports/{rep['id']}", headers=bob)).status_code == 404  # readable, not deletable
    await client.patch(f"/api/experiments/{exp['id']}", json={"is_public": False}, headers=alice)
    assert (await client.get(f"/api/reports/{rep['id']}", headers=bob)).status_code == 404  # un-publishing hides it at once
    assert (await client.delete(f"/api/reports/{rep['id']}", headers=alice)).status_code == 204
    assert (await client.get(f"/api/reports/{rep['id']}", headers=alice)).status_code == 404


async def test_report_download_headers_and_validation(client):
    exp = await make(client)
    rep = await report(client, exp["id"])
    r = await client.get(f"/api/reports/{rep['id']}/download")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    assert r.headers["x-content-type-options"] == "nosniff"
    disposition = r.headers["content-disposition"]
    assert 'attachment; filename="Research_report_arith.md"' in disposition
    assert (await client.post("/api/reports", json={})).status_code == 422
    assert (await client.post("/api/reports", json={"experiment_id": exp["id"], "investigation_id": str(uuid.uuid4())})).status_code == 422
    assert (await client.post("/api/reports", json={"experiment_id": str(uuid.uuid4())})).status_code == 404
    assert (await client.post("/api/reports", json={"investigation_id": str(uuid.uuid4())})).status_code == 401


async def test_exports_respect_visibility_and_label_mock_data(client):
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    exp = await make(client, alice)
    j = await client.get(f"/api/exports/experiments/{exp['id']}.json", headers=alice)
    body = j.json()
    assert j.status_code == 200 and body["export"]["contains_demo_data"] and "DEMO / MOCK" in body["export"]["notice"]
    assert body["experiment"]["seed"] == 3 and len(body["runs"]) == 72 and body["metrics"] and "owner" not in str(body).lower()
    assert 'attachment; filename="arith.json"' in j.headers["content-disposition"]
    c = await client.get(f"/api/exports/experiments/{exp['id']}/runs.csv", headers=alice)
    assert len(list(csv.reader(io.StringIO(c.text)))) == 73
    for path in (f"/api/exports/experiments/{exp['id']}.json", f"/api/exports/experiments/{exp['id']}/runs.csv"):
        assert (await client.get(path, headers=bob)).status_code == 404 and (await client.get(path)).status_code == 404
    mine = list(csv.reader(io.StringIO((await client.get("/api/exports/experiments.csv", headers=alice)).text)))
    theirs = list(csv.reader(io.StringIO((await client.get("/api/exports/experiments.csv", headers=bob)).text)))
    assert len(mine) == 2 and mine[1][1] == "arith" and len(theirs) == 1  # header only: nothing visible to bob


async def test_public_mode_report_caps():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.api.deps import get_adapter, get_engine
    from app.core.config import Settings
    from app.core.db import get_session
    from app.experiments.engine import ExperimentEngine
    from app.main import create_app
    from app.models import Base

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    app = create_app(Settings(public_demo_mode=True, public_max_reports_per_user=1, public_rate_limit_per_minute=1000,
                              auth_rate_limit_per_minute=1000))

    async def sess():
        async with maker() as s:
            yield s

    engine = ExperimentEngine(maker, lambda slug: MockAdapter(slug))
    app.dependency_overrides[get_session] = sess
    app.dependency_overrides[get_adapter] = lambda: MockAdapter()
    app.dependency_overrides[get_engine] = lambda: engine
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        h = await signup(c, "alice@example.com")
        e = (await c.post("/api/experiments", json={"name": "s", "task_type": "arithmetic_representation",
                                                    "config": {"n_random_pairs": 1}}, headers=h)).json()
        assert (await c.post("/api/reports", json={"experiment_id": e["id"]}, headers=h)).status_code == 201
        assert (await c.post("/api/reports", json={"experiment_id": e["id"]}, headers=h)).status_code == 429
    await eng.dispose()


